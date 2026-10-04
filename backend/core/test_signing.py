from unittest.mock import patch
from django.test import TestCase, override_settings
from django.db import DatabaseError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from . import tests as foundation
from .models import AuditEvent, Outbox, Role, SigningPlan, User
from .documents import generate
from .services import transition, revise, change_project_state
from .signing import prepare, status

@override_settings(DEBUG=True)
class SigningTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve
    def setup_review(self):
        self.manager.first_name='Review';self.manager.last_name='Manager';self.manager.email='manager@example.invalid';self.manager.save()
        self.comptroller.first_name='Review';self.comptroller.last_name='Comptroller';self.comptroller.email='comptroller@example.invalid';self.comptroller.save()
        self.im=User.objects.create_user(username='installer',role=Role.INSTALLATION_MANAGER,initials='IM',first_name='Installation',last_name='Manager',email='installer@example.invalid')
        self.approved=self.approve()
        for kind in ['CONTRACT','INVOICE','COMPLETION_NON_FINANCED']:
            generate(self.manager,self.approved.id,kind)
        self.input={'group':'COMMERCIAL','customer_name':'Authorized Customer','customer_email':'customer@example.invalid','gecc_signer':str(self.manager.id),'authority_note':'Synthetic test identity and signing authority reviewed.'}
    def test_commercial_bundles_both_documents_customer_first(self):
        self.setup_review();plan,created=prepare(self.manager,self.approved.id,self.input)
        self.assertTrue(created)
        preview=plan.review['envelope_preview'];signers=preview['recipients']['signers']
        self.assertEqual(len(preview['documents']),2)
        self.assertEqual([s['routingOrder'] for s in signers],['1','2'])
        for signer in signers:
            self.assertEqual([t['documentId'] for t in signer['tabs']['signHereTabs']],['1','2'])
            self.assertEqual(len(signer['tabs']['fullNameTabs']),2)
            self.assertEqual(len(signer['tabs']['dateSignedTabs']),2)
        self.assertEqual(preview['status'],'created')
        self.assertEqual(preview['notification']['expirations']['expireAfter'],'75')
        self.assertFalse(any('documentBase64' in d for d in preview['documents']))
        self.assertFalse(status(plan)['send_available']);self.assertIsNone(status(plan)['provider_status'])
        self.assertEqual(AuditEvent.objects.count(),Outbox.objects.count())
    def test_completion_gecc_first_and_finance_matches(self):
        self.setup_review()
        data={**self.input,'group':'COMPLETION_NON_FINANCED','gecc_signer':str(self.im.id)}
        plan,_=prepare(self.manager,self.approved.id,data)
        self.assertEqual([s['routingOrder'] for s in plan.review['envelope_preview']['recipients']['signers']],['2','1'])
        self.assertTrue(any('Work completion' in b for b in status(plan)['release_blockers']))
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,{**data,'group':'COMPLETION_FINANCED'})
    def test_comptroller_substitute_requires_reason(self):
        self.setup_review();data={**self.input,'group':'COMPLETION_NON_FINANCED','gecc_signer':str(self.comptroller.id)}
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,data)
        plan,_=prepare(self.manager,self.approved.id,{**data,'substitute_reason':'Installation Manager unavailable due to leave.'})
        self.assertIn('leave',plan.review['substitute_reason'])
    def test_identity_role_and_email_checks(self):
        self.setup_review()
        for updates in [{'customer_email':'invalid'},{'customer_email':self.manager.email.upper()},{'gecc_signer':'bad-uuid'},{'gecc_signer':str(self.sales.id)},{'gecc_signer':str(self.im.id)},{'authority_note':''},{'customer_name':['malformed']},{'group':['malformed']}]:
            with self.subTest(updates=updates),self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,{**self.input,**updates})
        self.manager.first_name='';self.manager.last_name='';self.manager.save()
        with self.assertRaises(ValidationError):prepare(self.comptroller,self.approved.id,self.input)
    def test_draft_and_missing_documents_rejected(self):
        self.manager.first_name='Review';self.manager.last_name='Manager';self.manager.email='manager@example.invalid';self.manager.save()
        data={'group':'COMMERCIAL','customer_name':'Customer','customer_email':'c@example.invalid','gecc_signer':str(self.manager.id),'authority_note':'Reviewed'}
        with self.assertRaisesMessage(ValidationError,'current approved'):
            prepare(self.manager,self.project.pending.id,data)
        approved=self.approve()
        with self.assertRaisesMessage(ValidationError,'Prepare the contract'):
            prepare(self.manager,approved.id,data)
        generate(self.manager,approved.id,'CONTRACT')
        with self.assertRaisesMessage(ValidationError,'Prepare the invoice'):
            prepare(self.manager,approved.id,data)
    def test_idempotent_and_audit_atomic(self):
        self.setup_review();first,_=prepare(self.manager,self.approved.id,self.input);before=AuditEvent.objects.count()
        second,created=prepare(self.manager,self.approved.id,self.input)
        self.assertFalse(created);self.assertEqual(first.id,second.id);self.assertEqual(before,AuditEvent.objects.count())
        with patch('core.signing.audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):prepare(self.manager,self.approved.id,{**self.input,'authority_note':'New review'})
        self.assertEqual(SigningPlan.objects.count(),1)
    def test_database_immutable(self):
        self.setup_review();plan,_=prepare(self.manager,self.approved.id,self.input)
        with self.assertRaises(DatabaseError),transaction.atomic():SigningPlan.objects.filter(pk=plan.pk).update(review={})
        with self.assertRaises(DatabaseError),transaction.atomic():SigningPlan.objects.filter(pk=plan.pk).delete()
    def test_revision_cancellation_and_signer_change_release_checks(self):
        self.setup_review();plan,_=prepare(self.manager,self.approved.id,self.input)
        self.manager.email='new@example.invalid';self.manager.save()
        self.assertEqual(status(plan)['status'],'REVIEW_REQUIRED')
        change_project_state(self.comptroller,self.project.id,'cancel','Customer cancelled','APPROVED')
        plan=SigningPlan.objects.select_related('msr__project').get(pk=plan.pk)
        self.assertEqual(status(plan)['status'],'CANCELLED')
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,self.input)
        change_project_state(self.comptroller,self.project.id,'reopen','Customer resumed','CANCELLED')
        revised=revise(self.sales,self.project.id,'Updated scope',str(self.approved.id));revised=transition(self.sales,revised.id,'submit',0);transition(self.comptroller,revised.id,'approve',revised.edit_sequence)
        plan=SigningPlan.objects.select_related('msr__project').get(pk=plan.pk)
        self.assertEqual(status(plan)['status'],'SUPERSEDED')
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,self.input)
    def test_scoped_api_and_read_only_history(self):
        self.setup_review();self.client.force_authenticate(self.manager)
        response=self.client.post(f'/api/msrs/{self.approved.id}/signing-reviews/',self.input,format='json');self.assertEqual(response.status_code,201)
        self.assertEqual(self.client.post(f'/api/msrs/{self.approved.id}/signing-reviews/',self.input,format='json').status_code,200)
        self.client.force_authenticate(self.sales)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.id}/signing-reviews/').status_code,200)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.id}/signing-candidates/').status_code,403)
        self.assertEqual(self.client.post(f'/api/msrs/{self.approved.id}/signing-reviews/',self.input,format='json').status_code,403)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.id}/signing-reviews/').status_code,404)
    def test_candidate_roles_and_account_changes(self):
        self.setup_review();self.client.force_authenticate(self.manager)
        path=f'/api/projects/{self.project.id}/signing-candidates/'
        self.assertEqual({u['role'] for u in self.client.get(path).json()},{Role.SALES_MANAGER,Role.COMPTROLLER})
        self.assertEqual({u['role'] for u in self.client.get(path+'?group=COMPLETION_NON_FINANCED').json()},{Role.INSTALLATION_MANAGER,Role.COMPTROLLER})
        self.im.is_active=False;self.im.save()
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,{**self.input,'group':'COMPLETION_NON_FINANCED','gecc_signer':str(self.im.id)})

    def test_changed_recipient_review_supersedes_previous(self):
        self.setup_review();first,_=prepare(self.manager,self.approved.id,self.input)
        second,_=prepare(self.manager,self.approved.id,{**self.input,'customer_email':'replacement@example.invalid'})
        self.assertEqual(status(first)['status'],'SUPERSEDED')
        self.assertEqual(status(second)['status'],'PREPARED')

    def test_malformed_input_rejected(self):
        self.setup_review()
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,[])
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.post(f'/api/msrs/{self.approved.id}/signing-reviews/',[],format='json').status_code,400)
