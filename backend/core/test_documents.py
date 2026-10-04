import copy
import hashlib
from io import BytesIO
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.db import DatabaseError, transaction, connection
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import tests as foundation
from .models import Document, AuditEvent, Outbox
from .services import transition, revise
from .documents import generate, render_pdf, canonical_hash

@override_settings(DEBUG=True)
class DocumentTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve
    def test_invoice_values_radio_and_signatures(self):
        self.snapshot.update(discount='500.00',tax='570.00',total_price='10070.00',customer_phone='301-555-0100',customer_email='customer@example.invalid')
        approved = self.approve()
        doc, created = generate(self.manager,approved.id,'INVOICE')
        self.assertTrue(created)
        reader = PdfReader(BytesIO(bytes(doc.content)));fields = reader.get_fields()
        for key, value in {'customer_name':'Example Customer','subtotal':'9,500.00','sales_tax':'570.00','invoice_total':'10,070.00','line_2_amount':'-500.00','payment_option':'/A','msr_version':'1.0'}.items():
            self.assertEqual(str(fields[key]['/V']),value)
        for key in ['customer_signature','gecc_signature']:
            self.assertEqual(fields[key]['/FT'],'/Sig')
            self.assertFalse(fields[key].get('/V'))
        self.assertEqual(doc.snapshot_sha256,canonical_hash(approved.snapshot))
        self.assertEqual(hashlib.sha256(bytes(doc.content)).hexdigest(),doc.pdf_sha256)
        self.assertGreaterEqual(len(reader.pages),2)
        self.assertIn('Install heat pump',' '.join(p.extract_text() for p in reader.pages))
    def test_contract_preserves_template_and_maps_terms(self):
        approved = self.approve()
        doc,_ = generate(self.manager,approved.id,'CONTRACT')
        reader = PdfReader(BytesIO(bytes(doc.content)));fields = reader.get_fields()
        self.assertGreaterEqual(len(reader.pages),4)
        self.assertEqual(fields['payment_option']['/V'],'50% deposit / 50% balance')
        self.assertEqual(fields['financing_type']['/V'],'Non-financed')
        self.assertFalse(fields['cancellation_deadline'].get('/V'))
        self.assertIn('five calendar days',' '.join(p.extract_text() for p in reader.pages).lower())
    def test_certificate_matching_finance_and_blank_completion_dates(self):
        approved = self.approve()
        doc,_ = generate(self.manager,approved.id,'COMPLETION_NON_FINANCED')
        fields = PdfReader(BytesIO(bytes(doc.content))).get_fields()
        for name in ['completion_date','customer_signed_date','gecc_signed_date','gecc_representative_name','gecc_substitute_reason']:
            self.assertFalse(fields[name].get('/V'))
        self.assertEqual(doc.status,'PREPARATION')
        with self.assertRaises(ValidationError):
            generate(self.manager,approved.id,'COMPLETION_FINANCED')
    def test_all_four_templates_render(self):
        approved = self.approve()
        for kind in ['INVOICE','CONTRACT','COMPLETION_NON_FINANCED']:
            generate(self.manager,approved.id,kind)
        revised = revise(self.sales,self.project.id,'Customer selected financing',str(approved.id))
        snap = {**revised.snapshot,'financing_type':'FINANCED'}
        revised = transition(self.sales,revised.id,'edit',0,snapshot=snap)
        revised = transition(self.sales,revised.id,'submit',revised.edit_sequence)
        revised = transition(self.manager,revised.id,'approve',revised.edit_sequence)
        doc,_ = generate(self.manager,revised.id,'COMPLETION_FINANCED')
        self.assertEqual(PdfReader(BytesIO(bytes(doc.content))).get_fields()['msr_version']['/V'],'2.0')
        self.assertEqual(Document.objects.count(),4)
    def test_draft_and_other_roles_cannot_generate(self):
        with self.assertRaises(ValidationError):
            generate(self.manager,self.project.pending.id,'INVOICE')
        approved=self.approve()
        for user in [self.sales,self.other]:
            with self.assertRaises(PermissionDenied):
                generate(user,approved.id,'INVOICE')
    def test_idempotent_generation_and_atomic_outbox(self):
        approved=self.approve()
        first,created=generate(self.manager,approved.id,'INVOICE')
        before=AuditEvent.objects.count()
        second,created=generate(self.manager,approved.id,'INVOICE')
        self.assertFalse(created);self.assertEqual(first.id,second.id)
        self.assertEqual(AuditEvent.objects.count(),before)
        self.assertEqual(AuditEvent.objects.count(),Outbox.objects.count())
        before_docs=Document.objects.count()
        with patch('core.documents.audit',side_effect=RuntimeError('Simulated audit failure')):
            with self.assertRaises(RuntimeError):
                generate(self.manager,approved.id,'CONTRACT')
        self.assertEqual(Document.objects.count(),before_docs)
    def test_document_database_immutability(self):
        approved=self.approve();doc,_=generate(self.manager,approved.id,'INVOICE')
        with self.assertRaises(DatabaseError), transaction.atomic():
            Document.objects.filter(pk=doc.pk).update(filename='tampered.pdf')
        with self.assertRaises(DatabaseError), transaction.atomic():
            Document.objects.filter(pk=doc.pk).delete()
    def test_download_scoped_and_old_documents_retained(self):
        approved=self.approve();doc,_=generate(self.manager,approved.id,'INVOICE')
        self.client.force_authenticate(self.sales)
        response=self.client.get(f'/api/documents/{doc.id}/download/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,bytes(doc.content))
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/documents/{doc.id}/download/').status_code,404)
        revised=revise(self.sales,self.project.id,'Scope correction',str(approved.id))
        revised=transition(self.sales,revised.id,'submit',0)
        transition(self.manager,revised.id,'approve',revised.edit_sequence)
        with self.assertRaises(ValidationError):
            generate(self.manager,approved.id,'CONTRACT')
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get(f'/api/documents/{doc.id}/download/').status_code,200)
    def test_master_customer_change_does_not_change_pdf(self):
        approved=self.approve()
        self.customer.legal_name='Changed customer';self.customer.phone='999';self.customer.save()
        doc,_=generate(self.manager,approved.id,'INVOICE')
        self.assertEqual(doc.values['customer_name'],'Example Customer')
        self.assertNotEqual(doc.values['customer_phone'],'999')
    def test_long_scope_is_not_truncated(self):
        self.snapshot['scope']='Detailed approved work. '*300
        approved=self.approve();doc,_=generate(self.manager,approved.id,'CONTRACT')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(bytes(doc.content))).pages)
        self.assertEqual(text.count('Detailed'),300)
        self.assertEqual(text.count('work.'),300)
    def test_generation_api_and_download(self):
        approved=self.approve()
        self.client.force_authenticate(self.manager)
        response=self.client.post(f'/api/msrs/{approved.id}/documents/',{'kind':'INVOICE'},format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.client.get(response.json()['download_url']).status_code,200)
        self.assertEqual(len(self.client.get(f'/api/projects/{self.project.id}/documents/').json()),1)
        self.assertEqual(self.client.post(f'/api/msrs/{approved.id}/documents/',{'kind':'INVOICE'},format='json').status_code,200)
    def test_commercial_widgets_have_values_appearances_and_readonly_flag(self):
        approved=self.approve();doc,_=generate(self.manager,approved.id,'INVOICE')
        reader=PdfReader(BytesIO(bytes(doc.content)));fields=reader.get_fields()
        for page in reader.pages:
            for ref in page.get('/Annots',[]):
                widget=ref.get_object();field=widget.get('/Parent',widget).get_object();name=field.get('/T')
                if name in doc.values:
                    self.assertEqual(str(field.get('/V','')),doc.values[name])
                    self.assertTrue(int(field.get('/Ff',0))&1)
                    self.assertIn('/N',widget['/AP'])
                if field.get('/FT')=='/Sig':
                    self.assertFalse(int(field.get('/Ff',0))&1)

    def test_missing_or_unapproved_private_template_is_rejected(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        approved=self.approve()
        with TemporaryDirectory() as directory:
            with patch('core.documents.TEMPLATE_DIR',Path(directory)):
                with self.assertRaises(ValidationError):
                    generate(self.manager,approved.id,'INVOICE')
                (Path(directory)/'GECC-HVAC-Invoice-Interactive.pdf').write_bytes(b'Not an approved template')
                with override_settings(DEBUG=False):
                    with self.assertRaises(ValidationError):
                        generate(self.manager,approved.id,'INVOICE')
    def test_legacy_approval_requires_revision_for_financing(self):
        self.snapshot.pop('financing_type',None)
        approved=self.approve()
        with self.assertRaises(ValidationError):
            generate(self.manager,approved.id,'CONTRACT')
        with self.assertRaises(ValidationError):
            generate(self.manager,approved.id,'COMPLETION_NON_FINANCED')
        generate(self.manager,approved.id,'INVOICE')


from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from django.db import close_old_connections, connections
from .models import User, AuditHead, LocalCounter

@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL document concurrency')
@override_settings(DEBUG=True)
class DocumentConcurrencyTests(TransactionTestCase):
    setUp = foundation.PostgreSQLConcurrencyTests.setUp
    def test_parallel_generation_returns_one_immutable_document(self):
        snapshot={**self.project.pending.snapshot,'scope':'Install replacement equipment','base_price':'100.00','total_price':'100.00','payment_terms':'100% at completion','payment_option':'100_PERCENT_COMPLETION'}
        item=transition(self.sales,self.project.pending.id,'edit',0,snapshot=snapshot)
        item=transition(self.sales,item.id,'submit',item.edit_sequence)
        item=transition(self.manager,item.id,'approve',item.edit_sequence)
        manager_id,msr_id=self.manager.id,item.id
        def prepare(_):
            close_old_connections()
            try:
                document,created=generate(User.objects.get(pk=manager_id),msr_id,'INVOICE')
                return document.id,created
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(prepare,range(2)))
        self.assertEqual(results[0][0],results[1][0])
        self.assertCountEqual([r[1] for r in results],[True,False])
        self.assertEqual(Document.objects.count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='document.generated').count(),1)
