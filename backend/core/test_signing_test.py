import base64
import copy
import json
import os
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from uuid import uuid4
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import signing_test as flow, release, docusign, test_release as fixtures, test_sandbox as sandbox_fixtures
from .models import (AuditEvent, Outbox, SigningTestPackage, SigningTestDecision,
                     SigningTestAttempt, SigningTestObservation, SigningTestDocument)
from .services import change_project_state

CONFIG={**sandbox_fixtures.CONFIG,'GECC_SANDBOX_TEST_EMAILS':'customer@testing-gecc.com,gecc@testing-gecc.com',
        'GECC_SANDBOX_SIGNING_SEND_ENABLED':'1'}

@override_settings(DEBUG=True)
class SigningTestTests(TestCase):
    setUp=fixtures.ReleaseTests.setUp
    edit_submit=fixtures.ReleaseTests.edit_submit
    approve=fixtures.ReleaseTests.approve
    setup_review=fixtures.ReleaseTests.setup_review
    setup_release=fixtures.ReleaseTests.setup_release
    approval=fixtures.ReleaseTests.approval
    oauth_responses=sandbox_fixtures.SandboxTests.oauth_responses

    def setup_test(self,completion=False):
        self.setup_release(completion);self.approval()
        self.data={'customer_email':'customer@testing-gecc.com','gecc_email':'gecc@testing-gecc.com',
                   'test_note':'Synthetic exact signing test only.','fictional_project_confirmed':True,'emails_controlled':True}
        with patch.dict(os.environ,CONFIG):self.test_package,_=flow.prepare(self.comptroller,self.package.id,self.data)

    def approve_test(self,actor=None):
        with patch.dict(os.environ,CONFIG):
            return flow.decide(actor or self.manager,self.test_package.id,{'decision':'APPROVED','note':'Synthetic test PDFs and emails reviewed.','exact_test_reviewed':True})

    def start(self,operation=flow.OP_SEND):
        with patch.dict(os.environ,CONFIG):result=flow.begin(self.comptroller,'synthetic-session',self.test_package.id,operation,True)
        return parse_qs(urlsplit(result['authorization_url']).query)['state'][0]

    def readings(self,eid=None,status='sent'):
        eid=eid or str(uuid4());expected=self.test_package.payload['envelope_preview']
        summary={'envelopeId':eid,'status':status,'lastModifiedDateTime':'2020-01-01T00:00:00Z'}
        recipients=copy.deepcopy(expected['recipients'])
        if status=='completed':
            summary['completedDateTime']='2020-01-01T00:00:00Z'
            for signer in recipients['signers']:signer.update(status='completed',signedDateTime='2020-01-01T00:00:00Z')
        return [summary,recipients,{'envelopeDocuments':copy.deepcopy(expected['documents'])},copy.deepcopy(summary)]

    def finish(self,state,data,send=False,pdf_error=False):
        responses=([{'envelopeId':data[0]['envelopeId'],'status':'sent'}]+data) if send else data
        pdf=base64.b64decode(self.test_package.payload['documents'][0]['documentBase64'])
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.signing_test.provider',side_effect=responses) as remote,patch('core.signing_test.pdf_document',side_effect=ValidationError('private-provider-body') if pdf_error else None,return_value=pdf) as download:
            result=docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        return result,remote,download

    def sent(self):
        self.setup_test();self.approve_test();self.finish(self.start(),self.readings(),send=True)
        return SigningTestAttempt.objects.get(package=self.test_package)

    def test_separate_test_pdfs_exact_emails_and_every_page_banner(self):
        self.setup_test(True)
        for entry in self.test_package.payload['documents']:
            reader=PdfReader(BytesIO(base64.b64decode(entry['documentBase64'])))
            for page in reader.pages:self.assertIn('SANDBOX SIGNING TEST',page.extract_text())
            text='\n'.join(page.extract_text() for page in reader.pages)
            self.assertIn(self.data['customer_email'],text);self.assertIn(self.data['gecc_email'],text)
            self.assertIn('Synthetic verification fixture',text)
            self.assertNotIn('SANDBOX TEST - DO NOT SIGN',text);self.assertNotIn('UNSIGNED RELEASE REVIEW',text)
            self.assertFalse(reader.get_fields()['customer_signature'].get('/V'))
        self.assertEqual(self.test_package.payload['review']['customer']['name'],'Authorized Customer')
        self.assertEqual(self.package.payload['purpose'],'UNSIGNED_RELEASE_REVIEW')
        self.assertEqual([s['routingOrder'] for s in self.test_package.payload['envelope_preview']['recipients']['signers']],['2','1'])

    def test_allowlist_fictional_confirmations_and_two_distinct_addresses(self):
        self.setup_test()
        for changes in [{'customer_email':'customer@example.invalid'},{'customer_email':'someone@outside-gecc.com'},
                        {'gecc_email':self.data['customer_email']},{'fictional_project_confirmed':False},
                        {'emails_controlled':'true'},{'test_note':''}]:
            with patch.dict(os.environ,CONFIG),self.subTest(changes=changes),self.assertRaises(ValidationError):flow.prepare(self.comptroller,self.package.id,{**self.data,**changes})
        with patch.dict(os.environ,{**CONFIG,'GECC_SANDBOX_TEST_EMAILS':''}),self.assertRaises(ValidationError):flow.policy()

    def test_independent_approval_required_and_default_send_disabled(self):
        self.setup_test()
        with patch.dict(os.environ,CONFIG):self.assertEqual(flow.describe(self.test_package)['status'],'REVIEW_REQUIRED')
        with self.assertRaises(PermissionDenied):self.approve_test(self.comptroller)
        with self.assertRaises(ValidationError):self.start()
        self.approve_test()
        with patch.dict(os.environ,{**CONFIG,'GECC_SANDBOX_SIGNING_SEND_ENABLED':'0'}):
            self.assertFalse(flow.describe(self.test_package)['send_available'])
            with self.assertRaises(ValidationError):flow.begin(self.comptroller,'session',self.test_package.id,flow.OP_SEND,True)

    def test_send_exact_reviewed_bytes_tabs_expiry_once(self):
        self.setup_test();self.approve_test();result,remote,_=self.finish(self.start(),self.readings(),send=True)
        self.assertEqual(result['status'],'SANDBOX_SIGNING_SENT');self.assertEqual(remote.call_count,5)
        payload=remote.call_args_list[0].kwargs['payload'];self.assertEqual(payload['status'],'sent')
        self.assertEqual(payload['notification']['expirations']['expireAfter'],'75')
        self.assertTrue(payload['emailSubject'].startswith('GECC SANDBOX SIGNING TEST'))
        for i,d in enumerate(payload['documents']):self.assertEqual(d['documentBase64'],self.test_package.payload['documents'][i]['documentBase64'])
        self.assertEqual(payload['recipients'],self.test_package.payload['envelope_preview']['recipients'])
        attempt=SigningTestAttempt.objects.get(package=self.test_package);self.assertEqual(payload['transactionId'],str(attempt.id));self.assertTrue(attempt.first_send_started_at)
        with self.assertRaises(ValidationError):self.start()

    def test_ambiguous_send_is_never_retried(self):
        self.setup_test();self.approve_test();state=self.start()
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.signing_test.provider',side_effect=TimeoutError('private-access-token')),self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        attempt=SigningTestAttempt.objects.get();self.assertEqual(attempt.state,'SEND_UNCERTAIN');self.assertTrue(attempt.first_send_started_at)
        with self.assertRaises(ValidationError):self.start()
        with self.assertRaises(ValidationError):self.start(flow.OP_READ)

    def test_failed_post_send_inspection_preserves_id_and_only_read_recovery(self):
        self.setup_test();self.approve_test();data=self.readings();data[1]['signers'][0]['email']='unexpected@testing-gecc.com'
        result,_,_=self.finish(self.start(),data,send=True)
        self.assertEqual(result['status'],'SANDBOX_SIGNING_READ_FAILED')
        attempt=SigningTestAttempt.objects.get();self.assertEqual(attempt.envelope_id,data[0]['envelopeId'])
        with self.assertRaises(ValidationError):self.start()
        result,remote,_=self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id))
        self.assertEqual(result['status'],'SANDBOX_SIGNING_SENT')
        self.assertTrue(all('payload' not in call.kwargs for call in remote.call_args_list))

    def test_completion_retains_all_documents_and_certificate_atomically(self):
        attempt=self.sent();result,_,download=self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,'completed'))
        self.assertEqual(result['status'],'SANDBOX_SIGNING_COMPLETED_RETAINED');self.assertEqual(download.call_count,3)
        self.assertEqual(set(SigningTestDocument.objects.values_list('document_id',flat=True)),{'1','2','certificate'})
        self.assertEqual(SigningTestObservation.objects.count(),2)
        with patch.dict(os.environ,CONFIG):metadata=flow.describe(self.test_package)
        self.assertEqual(len(metadata['attempt']['retained_documents']),3);self.assertFalse(metadata['send_available'])
        self.assertNotIn('documentBase64',json.dumps(metadata))
        state=self.start(flow.OP_READ);result,_,download=self.finish(state,self.readings(attempt.envelope_id,'completed'))
        self.assertEqual(download.call_count,0);self.assertEqual(SigningTestDocument.objects.count(),3)

    def test_incomplete_recipient_or_missing_certificate_retains_nothing(self):
        attempt=self.sent();data=self.readings(attempt.envelope_id,'completed');data[1]['signers'][0]['status']='sent'
        result,_,_=self.finish(self.start(flow.OP_READ),data);self.assertEqual(result['status'],'SANDBOX_SIGNING_READ_FAILED');self.assertFalse(SigningTestDocument.objects.exists())
        result,_,_=self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,'completed'),pdf_error=True)
        self.assertEqual(result['status'],'SANDBOX_SIGNING_READ_FAILED');self.assertFalse(SigningTestDocument.objects.exists())

    def test_decline_and_void_are_recorded_without_completed_retention(self):
        attempt=self.sent()
        for status in ['declined','voided']:
            result,_,download=self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,status))
            self.assertEqual(result['status'],'SANDBOX_SIGNING_'+status.upper());self.assertEqual(download.call_count,0)

    def test_no_tokens_provider_bodies_or_codes_retained(self):
        attempt=self.sent()
        stored=json.dumps(list(AuditEvent.objects.values('payload')))+json.dumps(list(SigningTestObservation.objects.values('evidence')))+json.dumps(self.test_package.payload)
        for value in ['synthetic-access-token','synthetic-refresh-token','synthetic-client-secret','synthetic-code']:
            self.assertNotIn(value,stored)
        self.assertEqual(AuditEvent.objects.count(),Outbox.objects.count())

    def test_explicit_confirmation_role_session_and_production_gates(self):
        self.setup_test();self.approve_test()
        with patch.dict(os.environ,CONFIG):
            with self.assertRaises(PermissionDenied):flow.begin(self.manager,'session',self.test_package.id,flow.OP_SEND,True)
            with self.assertRaises(ValidationError):flow.begin(self.comptroller,'session',self.test_package.id,flow.OP_SEND,'true')
            with self.assertRaises(ValidationError):flow.begin(self.comptroller,'',self.test_package.id,flow.OP_SEND,True)
            with override_settings(DEBUG=False),self.assertRaises(ValidationError):flow.begin(self.comptroller,'session',self.test_package.id,flow.OP_SEND,True)
        self.assertFalse(SigningTestAttempt.objects.exists())

    def test_revocation_and_changed_source_or_allowlist_block_before_network(self):
        self.setup_test();self.approve_test();state=self.start()
        release.decide(self.manager,self.package.id,{'decision':'REVOKED','note':'Synthetic source revoke'})
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.signing_test.provider') as remote,self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        remote.assert_not_called();self.assertIsNone(SigningTestAttempt.objects.get().first_send_started_at)

    def test_changed_test_approval_invalidates_pending_authorization(self):
        self.setup_test();self.approve_test();state=self.start()
        with patch.dict(os.environ,CONFIG):flow.decide(self.manager,self.test_package.id,{'decision':'REVOKED','note':'Synthetic revoke'})
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.signing_test.provider') as remote,self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        remote.assert_not_called()

    def test_latest_challenge_wins_and_replay_never_sends(self):
        self.setup_test();self.approve_test();old=self.start();new=self.start()
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.signing_test.provider') as remote,self.assertRaises(ValidationError):docusign.finish(self.comptroller,'synthetic-session',old,'synthetic-code')
        remote.assert_not_called();self.finish(new,self.readings(),send=True)
        with patch.dict(os.environ,CONFIG),patch('core.signing_test.provider') as remote,self.assertRaises(ValidationError):docusign.finish(self.comptroller,'synthetic-session',new,'synthetic-code')
        remote.assert_not_called()

    def test_read_stale_or_cancelled_sent_package_can_retain_history(self):
        attempt=self.sent();change_project_state(self.comptroller,self.project.id,'cancel','Synthetic cancellation','APPROVED')
        result,_,_=self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,'completed'))
        self.assertEqual(result['status'],'SANDBOX_SIGNING_COMPLETED_RETAINED')
        self.assertTrue(SigningTestObservation.objects.order_by('-created_at').first().evidence['local_review_blockers'])
        self.project.refresh_from_db();self.assertEqual(self.project.state,'CANCELLED')

    def test_all_retention_and_decision_records_database_immutable(self):
        attempt=self.sent();self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,'completed'))
        for model,field in [(SigningTestPackage,'digest'),(SigningTestDecision,'digest'),(SigningTestObservation,'digest'),(SigningTestDocument,'pdf_sha256')]:
            item=model.objects.first()
            with self.subTest(model=model),self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=item.id).update(**{field:'0'*64})
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=item.id).delete()

    def test_package_idempotence_and_audit_failure_rolls_back_approval(self):
        self.setup_test();before=AuditEvent.objects.count()
        with patch.dict(os.environ,CONFIG):p,created=flow.prepare(self.comptroller,self.package.id,self.data)
        self.assertFalse(created);self.assertEqual(p.id,self.test_package.id);self.assertEqual(AuditEvent.objects.count(),before)
        with patch('core.signing_test.audit',side_effect=RuntimeError('audit failed')),self.assertRaises(RuntimeError):self.approve_test()
        self.assertFalse(SigningTestDecision.objects.exists())

    def test_transport_fixed_sandbox_operations_and_pdf_bounds(self):
        with self.assertRaises(ValidationError):flow.provider(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],'','token',payload={'status':'created'})
        with self.assertRaises(ValidationError):flow.provider(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],str(uuid4()),'token',resource='/views/sender')
        with self.assertRaises(ValidationError):flow.pdf_document(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],str(uuid4()),'combined','token')
        with patch('core.signing_test.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'not a pdf'
            with self.assertRaises(ValidationError):flow.pdf_document(CONFIG['GECC_DOCUSIGN_ACCOUNT_ID'],str(uuid4()),'certificate','token')
            self.assertTrue(opener.return_value.open.call_args.args[0].full_url.startswith('https://demo.docusign.net/'))

    def test_api_scoping_private_downloads_and_no_raw_package_bytes(self):
        attempt=self.sent();self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,'completed'))
        self.client.force_authenticate(self.manager)
        with patch.dict(os.environ,CONFIG):response=self.client.get(f'/api/release-packages/{self.package.id}/signing-tests/')
        self.assertEqual(response.status_code,200);self.assertNotIn('documentBase64',response.content.decode())
        path=response.json()[0]['attempt']['retained_documents'][0]['download_url'];download=self.client.get(path)
        self.assertEqual(download.status_code,200);self.assertEqual(download['Cache-Control'],'private, no-store')
        self.client.force_authenticate(self.other);self.assertEqual(self.client.get(path).status_code,404)
        self.client.force_authenticate(self.manager)
        with patch.dict(os.environ,CONFIG):self.assertEqual(self.client.post(f'/api/signing-tests/{self.test_package.id}/connect/',{'operation':'READ','confirmed':True},format='json').status_code,403)

    def test_another_package_cannot_bypass_pending_send(self):
        self.sent()
        with patch.dict(os.environ,CONFIG):
            self.test_package,_=flow.prepare(self.comptroller,self.package.id,{**self.data,'test_note':'Synthetic second test'})
        self.approve_test()
        with self.assertRaisesMessage(ValidationError,'earlier signing test'):self.start()

    def test_during_read_changes_block_retention_and_newest_read_wins(self):
        attempt=self.sent();state=self.start(flow.OP_READ);responses=iter(self.readings(attempt.envelope_id,'completed'));calls=0
        def changed(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==4:self.start(flow.OP_READ)
            return next(responses)
        pdf=base64.b64decode(self.test_package.payload['documents'][0]['documentBase64'])
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=self.oauth_responses()),patch('core.signing_test.provider',side_effect=changed),patch('core.signing_test.pdf_document',return_value=pdf):
            result=docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        self.assertEqual(result['status'],'SANDBOX_SIGNING_SUPERSEDED');self.assertFalse(SigningTestDocument.objects.exists())
        attempt.refresh_from_db();self.assertEqual(attempt.state,'READ_PENDING')

    def test_failed_retention_audit_is_atomic_and_recoverable_by_read(self):
        attempt=self.sent();state=self.start(flow.OP_READ)
        # Only the final observation audit fails; the authorization already committed.
        with patch('core.signing_test.audit',side_effect=RuntimeError('audit unavailable')),self.assertRaises(RuntimeError):
            self.finish(state,self.readings(attempt.envelope_id,'completed'))
        self.assertFalse(SigningTestDocument.objects.exists());self.assertEqual(SigningTestObservation.objects.count(),1)
        attempt.refresh_from_db();self.assertEqual(attempt.state,'READ_PENDING')
        result,_,_=self.finish(self.start(flow.OP_READ),self.readings(attempt.envelope_id,'completed'))
        self.assertEqual(result['status'],'SANDBOX_SIGNING_COMPLETED_RETAINED')

    def test_provider_changes_during_retention_discard_bundle(self):
        attempt=self.sent();data=self.readings(attempt.envelope_id,'completed');data[3]['lastModifiedDateTime']='2020-01-02T00:00:00Z'
        result,_,_=self.finish(self.start(flow.OP_READ),data)
        self.assertEqual(result['status'],'SANDBOX_SIGNING_READ_FAILED');self.assertFalse(SigningTestDocument.objects.exists())

    def test_wrong_oauth_account_never_sends(self):
        self.setup_test();self.approve_test();state=self.start();responses=self.oauth_responses();responses[1]['accounts'][0]['account_id']=str(uuid4())
        with patch.dict(os.environ,CONFIG),patch('core.docusign.request_json',side_effect=responses),patch('core.signing_test.provider') as remote,self.assertRaises(ValidationError):
            docusign.finish(self.comptroller,'synthetic-session',state,'synthetic-code')
        remote.assert_not_called();self.assertIsNone(SigningTestAttempt.objects.get().first_send_started_at)
