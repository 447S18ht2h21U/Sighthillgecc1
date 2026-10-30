"""Historical contractor onboarding approval regression tests."""

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .contractor_services import (
    activate_contractor_engagement,
    approve_onboarding_document,
)
from .models import (
    Contractor,
    ContractorEngagement,
    ContractorOnboardingDocument,
    Role,
    User,
)


class ContractorHistoricalApprovalTests(TestCase):
    def setUp(self):
        self.original_reviewer = User.objects.create_user(
            username="historical_original_comptroller",
            password="test-only",
            role=Role.COMPTROLLER,
            initials="HC",
        )
        self.current_comptroller = User.objects.create_user(
            username="historical_current_comptroller",
            password="test-only",
            role=Role.COMPTROLLER,
            initials="NC",
        )
        self.sales_manager = User.objects.create_user(
            username="historical_sales_manager",
            password="test-only",
            role=Role.SALES_MANAGER,
            initials="SM",
        )

        self.contractor = Contractor.objects.create(
            contractor_number="CTR-HIST-001",
            legal_name="Historical Approval Test Contractor",
            created_by=self.original_reviewer,
        )
        self.engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code="CTR-HIST-001-01",
            role_description="Technical Associate",
            created_by=self.original_reviewer,
        )

        self.documents = []

        for kind in (
            ContractorOnboardingDocument.Kind.W9,
            ContractorOnboardingDocument.Kind.LICENSE_FRONT,
            ContractorOnboardingDocument.Kind.LICENSE_BACK,
            ContractorOnboardingDocument.Kind.AGREEMENT,
        ):
            document = ContractorOnboardingDocument.objects.create(
                engagement=self.engagement,
                kind=kind,
                storage_reference="test-only-document-reference",
            )
            approve_onboarding_document(
                self.original_reviewer,
                document.id,
            )
            self.documents.append(document)

    def verify_historical_evidence(self):
        for document in self.documents:
            document.refresh_from_db()
            self.assertEqual(
                document.status,
                ContractorOnboardingDocument.Status.APPROVED,
            )
            self.assertEqual(
                document.reviewed_by_id,
                self.original_reviewer.id,
            )
            self.assertIsNotNone(document.reviewed_at)

    def test_inactive_historical_reviewer_does_not_invalidate_approval(self):
        self.original_reviewer.is_active = False
        self.original_reviewer.save(update_fields=["is_active"])

        activate_contractor_engagement(
            self.current_comptroller,
            self.engagement.id,
        )

        self.engagement.refresh_from_db()
        self.assertEqual(
            self.engagement.status,
            ContractorEngagement.Status.ACTIVE,
        )
        self.verify_historical_evidence()

    def test_historical_reviewer_role_change_does_not_invalidate_approval(self):
        self.original_reviewer.role = Role.SALES_MANAGER
        self.original_reviewer.save(update_fields=["role"])

        activate_contractor_engagement(
            self.current_comptroller,
            self.engagement.id,
        )

        self.engagement.refresh_from_db()
        self.assertEqual(
            self.engagement.status,
            ContractorEngagement.Status.ACTIVE,
        )
        self.verify_historical_evidence()

    def test_unauthorized_manager_cannot_activate_historical_approvals(self):
        self.original_reviewer.is_active = False
        self.original_reviewer.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            activate_contractor_engagement(
                self.sales_manager,
                self.engagement.id,
            )

        self.engagement.refresh_from_db()
        self.assertEqual(
            self.engagement.status,
            ContractorEngagement.Status.PENDING,
        )
        self.verify_historical_evidence()