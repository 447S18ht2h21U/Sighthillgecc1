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
    def authorize_test_customer(self, group="COMMERCIAL", name="Authorized Customer", email="customer@example.invalid"):
        from .customer_signer_authorization_services import approve_customer_signer
        approver = self.manager if group == "COMMERCIAL" else self.comptroller
        return approve_customer_signer(
            project=self.project,
            customer=self.project.customer,
            group=group,
            signer_name=name,
            signer_email=email,
            authority_basis="Synthetic documented customer signing authority",
            evidence_reference="SYNTHETIC-SIGNING-TEST",
            requested_by=self.sales,
            approved_by=approver,
        )
    def setup_review(self):
        self.manager.first_name='Review';self.manager.last_name='Manager';self.manager.email='manager@example.invalid';self.manager.save()
        self.comptroller.first_name='Review';self.comptroller.last_name='Comptroller';self.comptroller.email='comptroller@example.invalid';self.comptroller.save()
        self.im=User.objects.create_user(username='installer',role=Role.INSTALLATION_MANAGER,initials='IM',first_name='Installation',last_name='Manager',email='installer@example.invalid')
        self.approved=self.approve()
        for kind in ['CONTRACT','INVOICE','COMPLETION_NON_FINANCED']:
            generate(self.manager,self.approved.id,kind)
        self.input={'group':'COMMERCIAL','customer_name':'Authorized Customer','customer_email':'customer@example.invalid','gecc_signer':str(self.manager.id),'authority_note':'Synthetic test identity and signing authority reviewed.'}
        self.commercial_authorization = self.authorize_test_customer()
        self.completion_authorization = self.authorize_test_customer(group="COMPLETION_NON_FINANCED")
    def test_plan_customer_authorization_valid(self):
        from .signing import validate_plan_customer_authorization

        self.setup_review()
        plan, created = prepare(self.manager, self.approved.id, self.input)

        self.assertTrue(created)
        authorization = validate_plan_customer_authorization(plan)
        self.assertEqual(authorization.pk, self.commercial_authorization.pk)
        self.assertEqual(
            plan.review["customer_authorization_id"],
            str(authorization.pk),
        )
        self.assertEqual(
            plan.review["customer_authorization_digest"],
            authorization.digest,
        )
    def test_plan_customer_authorization_revoked(self):
        from .customer_signer_authorization_services import revoke_customer_signer
        from .signing import validate_plan_customer_authorization

        self.setup_review()
        plan, created = prepare(self.manager, self.approved.id, self.input)
        self.assertTrue(created)
        self.assertEqual(
            validate_plan_customer_authorization(plan).pk,
            self.commercial_authorization.pk,
        )

        original_review = plan.review.copy()
        original_digest = plan.digest

        revocation = revoke_customer_signer(
            authorization_id=self.commercial_authorization.pk,
            revoked_by=self.manager,
            reason="Synthetic withdrawal of customer signing authority.",
        )

        self.assertEqual(
            revocation.authorization_id,
            self.commercial_authorization.pk,
        )

        with self.assertRaisesMessage(ValidationError, "revoked"):
            validate_plan_customer_authorization(plan)

        plan.refresh_from_db()
        self.assertEqual(plan.review, original_review)
        self.assertEqual(plan.digest, original_digest)
    def test_plan_customer_authorization_mismatch(self):
        from copy import deepcopy
        from uuid import uuid4
        from .signing import validate_plan_customer_authorization

        self.setup_review()
        plan, _ = prepare(self.manager, self.approved.id, self.input)
        original_review = deepcopy(plan.review)
        original_group = plan.group

        cases = (
            ("authorization_id", {"customer_authorization_id": str(uuid4())}),
            ("authorization_digest", {"customer_authorization_digest": "0" * 64}),
            ("customer_name", {"customer": {**original_review["customer"], "name": "Different Customer"}}),
            ("customer_email", {"customer": {**original_review["customer"], "email": "different@example.invalid"}}),
        )

        try:
            for label, changes in cases:
                with self.subTest(case=label):
                    plan.review = {**original_review, **changes}
                    with self.assertRaises(ValidationError):
                        validate_plan_customer_authorization(plan)

            plan.review = original_review
            plan.group = "COMPLETION_NON_FINANCED"
            with self.assertRaises(ValidationError):
                validate_plan_customer_authorization(plan)
        finally:
            plan.review = original_review
            plan.group = original_group

        self.assertEqual(
            validate_plan_customer_authorization(plan).pk,
            self.commercial_authorization.pk,
        )
        plan.refresh_from_db()
        self.assertEqual(plan.review, original_review)
    def test_revoked_customer_authorization_blocks_signing_status(self):
        from copy import deepcopy
        from .customer_signer_authorization_services import revoke_customer_signer

        self.setup_review()
        plan, created = prepare(self.manager, self.approved.id, self.input)
        self.assertTrue(created)
        self.assertEqual(status(plan)["status"], "PREPARED")

        original_review = deepcopy(plan.review)
        original_digest = plan.digest

        revoke_customer_signer(
            authorization_id=self.commercial_authorization.pk,
            revoked_by=self.manager,
            reason="Synthetic withdrawal before document signing.",
        )

        result = status(plan)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["send_available"])
        self.assertTrue(
            any("authorization is invalid or revoked" in blocker
                for blocker in result["release_blockers"])
        )

        plan.refresh_from_db()
        self.assertEqual(plan.review, original_review)
        self.assertEqual(plan.digest, original_digest)
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
        self.authorize_test_customer(name="Customer", email="c@example.invalid")
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
        self.authorize_test_customer(email="replacement@example.invalid")
        second,_=prepare(self.manager,self.approved.id,{**self.input,'customer_email':'replacement@example.invalid'})
        self.assertEqual(status(first)['status'],'SUPERSEDED')
        self.assertEqual(status(second)['status'],'PREPARED')

    def test_malformed_input_rejected(self):
        self.setup_review()
        with self.assertRaises(ValidationError):prepare(self.manager,self.approved.id,[])
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.post(f'/api/msrs/{self.approved.id}/signing-reviews/',[],format='json').status_code,400)
