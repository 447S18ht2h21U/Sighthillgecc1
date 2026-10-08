from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .models import Contractor, ContractorEngagement, Role, User
from .contractor_services import activate_contractor_engagement


class ContractorOnboardingTests(TestCase):

    def test_activation_requires_all_four_documents(self):
        comptroller = User.objects.create_user(
            username='test_contractor_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='TC',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-001',
            legal_name='Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-001-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        with self.assertRaises(ValidationError):
            activate_contractor_engagement(comptroller, engagement.id)

        engagement.refresh_from_db()

        self.assertEqual(
            engagement.status,
            ContractorEngagement.Status.PENDING,
        )

    def test_activation_rejects_three_approved_documents(self):
        from .models import ContractorOnboardingDocument

        comptroller = User.objects.create_user(
            username='test_partial_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='PC',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-002',
            legal_name='Partial Onboarding Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-002-01',
            role_description='Sales Associate',
            created_by=comptroller,
        )

        for kind in (
            ContractorOnboardingDocument.Kind.W9,
            ContractorOnboardingDocument.Kind.LICENSE_FRONT,
            ContractorOnboardingDocument.Kind.LICENSE_BACK,
        ):
            ContractorOnboardingDocument.objects.create(
                engagement=engagement,
                kind=kind,
                storage_reference='test-only-reference',
                status=ContractorOnboardingDocument.Status.APPROVED,
                reviewed_by=comptroller,
                reviewed_at=__import__('django.utils.timezone', fromlist=['now']).now(),
            )

        with self.assertRaises(ValidationError):
            activate_contractor_engagement(comptroller, engagement.id)

        engagement.refresh_from_db()

        self.assertEqual(
            engagement.status,
            ContractorEngagement.Status.PENDING,
        )

    def test_activation_succeeds_with_four_approved_documents(self):
        from django.utils import timezone
        from .models import ContractorOnboardingDocument

        comptroller = User.objects.create_user(
            username='test_full_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='FC',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-003',
            legal_name='Fully Onboarded Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-003-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        for kind in (
            ContractorOnboardingDocument.Kind.W9,
            ContractorOnboardingDocument.Kind.LICENSE_FRONT,
            ContractorOnboardingDocument.Kind.LICENSE_BACK,
            ContractorOnboardingDocument.Kind.AGREEMENT,
        ):
            ContractorOnboardingDocument.objects.create(
                engagement=engagement,
                kind=kind,
                storage_reference='test-only-reference',
                status=ContractorOnboardingDocument.Status.APPROVED,
                reviewed_by=comptroller,
                reviewed_at=timezone.now(),
            )

        activate_contractor_engagement(comptroller, engagement.id)

        engagement.refresh_from_db()

        self.assertEqual(
            engagement.status,
            ContractorEngagement.Status.ACTIVE,
        )
        from .models import AuditEvent

        event = AuditEvent.objects.get(
            action='contractor.engagement.activated',
            entity_id=engagement.id,
        )

        self.assertEqual(event.actor_id, comptroller.id)
        self.assertEqual(
            event.payload['contractor_id'],
            str(contractor.id),
        )
        self.assertEqual(
            event.payload['engagement_code'],
            engagement.engagement_code,
        )

    def test_sales_manager_cannot_activate_engagement(self):
        from rest_framework.exceptions import PermissionDenied

        comptroller = User.objects.create_user(
            username='test_authorizing_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='AC',
        )

        manager = User.objects.create_user(
            username='test_unauthorized_manager',
            password='TestPassword123!',
            role=Role.SALES_MANAGER,
            initials='UM',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-004',
            legal_name='Authorization Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-004-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        with self.assertRaises(PermissionDenied):
            activate_contractor_engagement(manager, engagement.id)

        engagement.refresh_from_db()

        self.assertEqual(
            engagement.status,
            ContractorEngagement.Status.PENDING,
        )

    def test_sales_manager_denied_even_with_all_documents_approved(self):
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .models import ContractorOnboardingDocument

        comptroller = User.objects.create_user(
            username='test_full_docs_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='FD',
        )

        manager = User.objects.create_user(
            username='test_full_docs_manager',
            password='TestPassword123!',
            role=Role.SALES_MANAGER,
            initials='FM',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-005',
            legal_name='Authorization Boundary Test',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-005-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        for kind in (
            ContractorOnboardingDocument.Kind.W9,
            ContractorOnboardingDocument.Kind.LICENSE_FRONT,
            ContractorOnboardingDocument.Kind.LICENSE_BACK,
            ContractorOnboardingDocument.Kind.AGREEMENT,
        ):
            ContractorOnboardingDocument.objects.create(
                engagement=engagement,
                kind=kind,
                storage_reference='test-only-reference',
                status=ContractorOnboardingDocument.Status.APPROVED,
                reviewed_by=comptroller,
                reviewed_at=timezone.now(),
            )

        with self.assertRaises(PermissionDenied):
            activate_contractor_engagement(manager, engagement.id)

        engagement.refresh_from_db()

        self.assertEqual(
            engagement.status,
            ContractorEngagement.Status.PENDING,
        )

    def test_sales_manager_cannot_approve_onboarding_document(self):
        from rest_framework.exceptions import PermissionDenied
        from .models import ContractorOnboardingDocument
        from .contractor_services import approve_onboarding_document

        comptroller = User.objects.create_user(
            username='test_document_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='DC',
        )

        manager = User.objects.create_user(
            username='test_document_manager',
            password='TestPassword123!',
            role=Role.SALES_MANAGER,
            initials='DM',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-006',
            legal_name='Document Approval Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-006-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        document = ContractorOnboardingDocument.objects.create(
            engagement=engagement,
            kind=ContractorOnboardingDocument.Kind.W9,
            storage_reference='test-only-reference',
        )

        with self.assertRaises(PermissionDenied):
            approve_onboarding_document(manager, document.id)

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            ContractorOnboardingDocument.Status.PENDING,
        )
        self.assertIsNone(document.reviewed_by)
        self.assertIsNone(document.reviewed_at)

    def test_comptroller_approval_records_audit_event(self):
        from .models import ContractorOnboardingDocument, AuditEvent
        from .contractor_services import approve_onboarding_document

        comptroller = User.objects.create_user(
            username='test_approval_comptroller',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='CA',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-007',
            legal_name='Approval Audit Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-007-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        document = ContractorOnboardingDocument.objects.create(
            engagement=engagement,
            kind=ContractorOnboardingDocument.Kind.W9,
            storage_reference='test-only-reference',
        )

        approve_onboarding_document(comptroller, document.id)

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            ContractorOnboardingDocument.Status.APPROVED,
        )
        self.assertEqual(document.reviewed_by_id, comptroller.id)
        self.assertIsNotNone(document.reviewed_at)

        event = AuditEvent.objects.get(
            action='contractor.document.approved',
            entity_id=document.id,
        )

        self.assertEqual(event.actor_id, comptroller.id)
        self.assertEqual(
            event.payload['engagement_id'],
            str(engagement.id),
        )
        self.assertEqual(
            event.payload['document_kind'],
            ContractorOnboardingDocument.Kind.W9,
        )

    def test_document_cannot_be_approved_twice(self):
        from rest_framework.exceptions import ValidationError
        from .models import ContractorOnboardingDocument, AuditEvent
        from .contractor_services import approve_onboarding_document

        comptroller = User.objects.create_user(
            username='test_duplicate_approval',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='DA',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-008',
            legal_name='Duplicate Approval Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-008-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        document = ContractorOnboardingDocument.objects.create(
            engagement=engagement,
            kind=ContractorOnboardingDocument.Kind.W9,
            storage_reference='test-only-reference',
        )

        approve_onboarding_document(comptroller, document.id)

        with self.assertRaises(ValidationError):
            approve_onboarding_document(comptroller, document.id)

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            ContractorOnboardingDocument.Status.APPROVED,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                action='contractor.document.approved',
                entity_id=document.id,
            ).count(),
            1,
        )

    def test_document_without_storage_reference_cannot_be_approved(self):
        from rest_framework.exceptions import ValidationError
        from .models import ContractorOnboardingDocument, AuditEvent
        from .contractor_services import approve_onboarding_document

        comptroller = User.objects.create_user(
            username='test_missing_document_reference',
            password='TestPassword123!',
            role=Role.COMPTROLLER,
            initials='MR',
        )

        contractor = Contractor.objects.create(
            contractor_number='CTR-TEST-009',
            legal_name='Missing Reference Test Contractor',
            created_by=comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code='CTR-TEST-009-01',
            role_description='Technical Associate',
            created_by=comptroller,
        )

        document = ContractorOnboardingDocument.objects.create(
            engagement=engagement,
            kind=ContractorOnboardingDocument.Kind.W9,
            storage_reference='',
        )

        with self.assertRaises(ValidationError):
            approve_onboarding_document(comptroller, document.id)

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            ContractorOnboardingDocument.Status.PENDING,
        )
        self.assertIsNone(document.reviewed_by)
        self.assertIsNone(document.reviewed_at)

        self.assertFalse(
            AuditEvent.objects.filter(
                action='contractor.document.approved',
                entity_id=document.id,
            ).exists()
        )
