import base64
from io import BytesIO
from unittest.mock import patch
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import release, tests as foundation, test_signing as signing_tests
from .models import AuditEvent, ProjectEvidence, ReleasePackage, ReleaseApproval
from .services import change_project_state, revise, transition
from .signing import prepare

@override_settings(DEBUG=True)
class ReleaseTests(TestCase):
    setUp=foundation.FoundationTests.setUp
    edit_submit=foundation.FoundationTests.edit_submit
    approve=foundation.FoundationTests.approve
    setup_review=signing_tests.SigningTests.setup_review
    def setup_release(self,completion=False):
        self.setup_review();data={**self.input}
        if completion:data.update(group='COMPLETION_NON_FINANCED',gecc_signer=str(self.comptroller.id),substitute_reason='Synthetic IM unavailable')
        self.plan,_=prepare(self.manager,self.approved.id,data)
        self.evidence_data={'kind':'WORK_COMPLETION' if completion else 'CANCELLATION_DEADLINE','verified':True,
            'source_reference':'Synthetic verification fixture','verification_note':'Test attestation only, not actual work or legal review.',
            'deadline':'2026-10-20T23:59:00-04:00','notice_and_applicability_checked':True,
            'completion_date':'2020-01-01','work_verified':True,'permits_inspections_checked':True,'exceptions_resolved':True,'substitute_reason':'Synthetic IM unavailable'}
        self.evidence,_=release.record_evidence(self.comptroller,self.approved.id,self.evidence_data)
        self.package,_=release.prepare_package(self.comptroller,self.plan.id)
    def approval(self,actor=None):
        return release.decide(actor or self.manager,self.package.id,{'decision':'APPROVED','note':'Synthetic exact documents and evidence reviewed.','documents_and_evidence_reviewed':True})
    def test_commercial_deadline_and_exact_signers_bound_into_pdf(self):
        self.setup_release()
        contract=self.package.payload['documents'][0]
        fields=PdfReader(BytesIO(base64.b64decode(contract['documentBase64']))).get_fields()
        self.assertEqual(fields['cancellation_deadline']['/V'],self.evidence.data['deadline'])
        self.assertEqual(fields['customer_printed_name']['/V'],'Authorized Customer')
        self.assertFalse(fields['customer_signature'].get('/V'))
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(base64.b64decode(contract['documentBase64']))).pages)
        self.assertIn('Manual attestation',text);self.assertIn('Synthetic verification fixture',text);self.assertIn('UNSIGNED RELEASE REVIEW',text)
        self.assertEqual(release.status(self.package)['status'],'REVIEW_REQUIRED')
        self.assertNotIn('documentBase64',str(release.describe(self.package)))
    def test_completion_date_fields_and_exceptions_verification(self):
        self.setup_release(True)
        fields=PdfReader(BytesIO(base64.b64decode(self.package.payload['documents'][0]['documentBase64']))).get_fields()
        self.assertEqual(fields['completion_date']['/V'],'2020-01-01');self.assertEqual(fields['gecc_role']['/V'],'Comptroller')
        self.assertIn('resolved',fields['completion_exceptions']['/V'])
        self.assertFalse(fields['gecc_signed_date'].get('/V'))
    def test_two_person_approval_never_enables_sending(self):
        self.setup_release()
        with self.assertRaises(PermissionDenied):self.approval(self.comptroller)
        decision,created=self.approval();self.assertTrue(created)
        self.assertEqual(decision.package_digest,self.package.digest)
        self.assertEqual(release.status(self.package)['status'],'APPROVED');self.assertFalse(release.status(self.package)['send_available'])
        again,created=self.approval();self.assertFalse(created);self.assertEqual(again.id,decision.id)
    def test_evidence_and_package_idempotence_and_audit_atomicity(self):
        self.setup_release();before=AuditEvent.objects.count()
        e,created=release.record_evidence(self.comptroller,self.approved.id,self.evidence_data);self.assertFalse(created);self.assertEqual(e.id,self.evidence.id)
        p,created=release.prepare_package(self.comptroller,self.plan.id);self.assertFalse(created);self.assertEqual(p.id,self.package.id)
        self.assertEqual(AuditEvent.objects.count(),before)
        with patch('core.release.audit',side_effect=RuntimeError('audit failed')),self.assertRaises(RuntimeError):self.approval()
        self.assertFalse(ReleaseApproval.objects.exists())
        with patch('core.release.audit',side_effect=RuntimeError('audit failed')),self.assertRaises(RuntimeError):release.record_evidence(self.comptroller,self.approved.id,{**self.evidence_data,'verification_note':'Different note'})
        self.assertEqual(ProjectEvidence.objects.count(),1)
    def test_database_immutability_all_three_records(self):
        self.setup_release();decision,_=self.approval()
        for model,item,field in [(ProjectEvidence,self.evidence,'digest'),(ReleasePackage,self.package,'digest'),(ReleaseApproval,decision,'digest')]:
            with self.subTest(model=model),self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=item.id).update(**{field:'0'*64})
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=item.id).delete()
    def test_deadline_requires_offset_notice_review_and_provenance(self):
        self.setup_release()
        for update in [{'deadline':'2026-10-20T23:59:00'},{'deadline':'invalid'},{'notice_and_applicability_checked':False},{'source_reference':''},{'verified':'true'},{'kind':[]}]:
            with self.subTest(update=update),self.assertRaises(ValidationError):release.record_evidence(self.comptroller,self.approved.id,{**self.evidence_data,**update})
        with self.assertRaises(PermissionDenied):release.record_evidence(self.manager,self.approved.id,self.evidence_data)
    def test_completion_checks_future_and_incomplete_work_rejected(self):
        self.setup_release(True)
        for update in [{'completion_date':'9999-01-01'},{'work_verified':False},{'permits_inspections_checked':False},{'exceptions_resolved':False},{'substitute_reason':''}]:
            with self.subTest(update=update),self.assertRaises(ValidationError):release.record_evidence(self.comptroller,self.approved.id,{**self.evidence_data,**update})
    def test_changed_or_withdrawn_evidence_invalidates_approval(self):
        self.setup_release();self.approval()
        release.record_evidence(self.comptroller,self.approved.id,{**self.evidence_data,'deadline':'2026-10-21T23:59:00-04:00'})
        self.assertEqual(release.status(self.package)['status'],'BLOCKED')
        new,_=release.prepare_package(self.comptroller,self.plan.id);self.assertNotEqual(new.id,self.package.id)
        self.assertEqual(release.status(new)['status'],'REVIEW_REQUIRED')
        release.record_evidence(self.comptroller,self.approved.id,{**self.evidence_data,'verified':False})
        self.assertEqual(release.status(new)['status'],'BLOCKED')
        with self.assertRaises(ValidationError):release.prepare_package(self.comptroller,self.plan.id)
        release.validate_package(self.package,check_current=False)
    def test_revocation_is_new_immutable_decision(self):
        self.setup_release();first,_=self.approval()
        revoked,_=release.decide(self.comptroller,self.package.id,{'decision':'REVOKED','note':'Synthetic withdrawal'})
        self.assertNotEqual(first.id,revoked.id);self.assertEqual(ReleaseApproval.objects.count(),2)
        self.assertEqual(release.status(self.package)['status'],'REVOKED')
    def test_changed_review_cancelled_project_and_reviewer_block(self):
        self.setup_release();self.approval();self.manager.is_active=False;self.manager.save()
        self.assertEqual(release.status(self.package)['status'],'BLOCKED')
        self.manager.is_active=True;self.manager.save()
        prepare(self.manager,self.approved.id,{**self.input,'customer_name':'New Customer'})
        self.assertEqual(release.status(self.package)['status'],'BLOCKED')
        change_project_state(self.comptroller,self.project.id,'cancel','Synthetic cancellation','APPROVED')
        with self.assertRaises(ValidationError):release.record_evidence(self.comptroller,self.approved.id,self.evidence_data)
    def test_msr_revision_requires_new_evidence(self):
        self.setup_release();item=revise(self.sales,self.project.id,'Synthetic revision',str(self.approved.id))
        item=transition(self.sales,item.id,'submit',0);transition(self.comptroller,item.id,'approve',item.edit_sequence)
        self.package=ReleasePackage.objects.select_related('plan__msr__project').get(pk=self.package.id)
        self.assertEqual(release.status(self.package)['status'],'BLOCKED')
        self.assertFalse(ProjectEvidence.objects.filter(msr=item).exists())
    def test_missing_evidence_and_explicit_review_required(self):
        self.setup_review();plan,_=prepare(self.manager,self.approved.id,self.input)
        with self.assertRaises(ValidationError):release.prepare_package(self.comptroller,plan.id)
        release.record_evidence(self.comptroller,self.approved.id,{'kind':'CANCELLATION_DEADLINE','verified':True,'source_reference':'Synthetic','verification_note':'Synthetic','deadline':'2026-10-20T23:59:00-04:00','notice_and_applicability_checked':True})
        package,_=release.prepare_package(self.comptroller,plan.id)
        with self.assertRaises(ValidationError):release.decide(self.manager,package.id,{'decision':'APPROVED','note':'Reviewed'})
    def test_scoped_api_permissions_and_historical_download(self):
        self.setup_release();self.client.force_authenticate(self.manager)
        evidence_path=f'/api/msrs/{self.approved.id}/verification-evidence/'
        self.assertEqual(self.client.get(evidence_path).status_code,200)
        self.assertEqual(self.client.post(evidence_path,self.evidence_data,format='json').status_code,403)
        path=release.describe(self.package)['documents'][0]['download_url']
        self.assertEqual(self.client.get(path).status_code,200)
        self.client.force_authenticate(self.other);self.assertEqual(self.client.get(path).status_code,404);self.assertEqual(self.client.get(evidence_path).status_code,404)
        self.client.force_authenticate(self.sales);self.assertEqual(self.client.post(f'/api/signing-reviews/{self.plan.id}/release-packages/',{},format='json').status_code,403)
    def test_production_and_tampered_package_rejected(self):
        self.setup_release()
        with override_settings(DEBUG=False),self.assertRaises(ValidationError):release.record_evidence(self.comptroller,self.approved.id,self.evidence_data)
        self.package.payload['purpose']='changed'
        with self.assertRaises(ValidationError):release.validate_package(self.package)
