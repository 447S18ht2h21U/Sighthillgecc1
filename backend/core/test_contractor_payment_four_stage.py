"""Four-stage contractor payment service acceptance tests."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .contractor_payment_services import (
    create_contractor_payment_record,
    approve_contractor_payment_record,
    mark_contractor_payment_paid,
)
from .contractor_payment_issuance_services import issue_contractor_payment
from .contractor_payment_settlement_services import (
    verify_contractor_payment_settlement,
)
from .models import (
    Contractor,
    ContractorEngagement,
    ContractorCompensationPlan,
    ContractorPaymentRecord,
    ContractorPaymentIssuance,
    ContractorPaymentSettlementVerification,
    Role,
    User,
)


class ContractorPaymentFourStageTests(TestCase):
    """Test independent issuance and settlement controls."""

    def setUp(self):
        self.ceo = User.objects.create_user(
            username="four_stage_ceo",
            role=Role.CEO,
        )
        self.comptroller = User.objects.create_user(
            username="four_stage_comptroller",
            role=Role.COMPTROLLER,
        )

        self.contractor = Contractor.objects.create(
            contractor_number="CTR-FOUR-STAGE-001",
            legal_name="Four Stage Test Contractor",
            created_by=self.comptroller,
        )
        self.engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code="ENG-FOUR-STAGE-001",
            role_description="Contractor payment acceptance test",
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )
        self.plan = ContractorCompensationPlan.objects.create(
            engagement=self.engagement,
            version=1,
            effective_date=date(2026, 10, 1),
            compensation_terms={"amount": "125.00"},
            status=ContractorCompensationPlan.Status.APPROVED,
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )

        self.payment = create_contractor_payment_record(
            self.comptroller,
            self.engagement,
            self.plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal("125.00"),
            Decimal("0.00"),
            Decimal("125.00"),
            {"source": "FOUR_STAGE_ACCEPTANCE_TEST"},
        )

    def approve(self):
        return approve_contractor_payment_record(
            self.ceo, self.payment.pk
        )

    def issue(self):
        return issue_contractor_payment(
            self.ceo,
            self.payment.pk,
            Decimal("125.00"),
            ContractorPaymentIssuance.Method.ACH,
            "FOUR-STAGE-TEST-ACH-001",
            "Temporary test issuance evidence",
        )

    def verify(self):
        return verify_contractor_payment_settlement(
            self.comptroller,
            self.payment.pk,
            date.today(),
            Decimal("125.00"),
            "FOUR-STAGE-TEST-BANK-001",
        )

    def test_draft_requires_ceo_approval_before_issuance(self):
        with self.assertRaises(ValidationError):
            self.issue()

        self.assertFalse(
            ContractorPaymentIssuance.objects.filter(
                payment_record=self.payment
            ).exists()
        )

    def test_approved_payment_cannot_be_marked_paid_without_issuance(self):
        self.approve()

        with self.assertRaises(ValidationError):
            mark_contractor_payment_paid(
                self.comptroller, self.payment.pk
            )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

    def test_issued_payment_cannot_be_marked_paid_without_settlement(self):
        self.approve()
        self.issue()

        with self.assertRaises(ValidationError):
            mark_contractor_payment_paid(
                self.comptroller, self.payment.pk
            )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

    def test_comptroller_cannot_issue_payment(self):
        self.approve()

        with self.assertRaises(PermissionDenied):
            issue_contractor_payment(
                self.comptroller,
                self.payment.pk,
                Decimal("125.00"),
                "ACH",
                "UNAUTHORIZED-ISSUANCE",
            )

    def test_ceo_cannot_verify_settlement(self):
        self.approve()
        self.issue()

        with self.assertRaises(PermissionDenied):
            verify_contractor_payment_settlement(
                self.ceo,
                self.payment.pk,
                date.today(),
                Decimal("125.00"),
                "UNAUTHORIZED-BANK-REFERENCE",
            )

    def test_issuance_amount_must_match_approved_payment(self):
        self.approve()

        with self.assertRaises(ValidationError):
            issue_contractor_payment(
                self.ceo,
                self.payment.pk,
                Decimal("124.00"),
                "ACH",
                "WRONG-AMOUNT",
            )

    def test_settlement_amount_must_match_issuance(self):
        self.approve()
        self.issue()

        with self.assertRaises(ValidationError):
            verify_contractor_payment_settlement(
                self.comptroller,
                self.payment.pk,
                date.today(),
                Decimal("124.00"),
                "WRONG-CLEARED-AMOUNT",
            )

    def test_full_four_stage_payment_workflow(self):
        self.approve()
        issuance = self.issue()
        verification = self.verify()

        self.assertEqual(
            issuance.issued_by_id, self.ceo.pk
        )
        self.assertEqual(
            verification.verified_by_id, self.comptroller.pk
        )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

        mark_contractor_payment_paid(
            self.comptroller, self.payment.pk
        )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.PAID,
        )
        self.assertIsNotNone(self.payment.paid_at)

    def test_duplicate_issuance_is_rejected(self):
        self.approve()
        self.issue()

        with self.assertRaises(ValidationError):
            self.issue()

    def test_duplicate_settlement_verification_is_rejected(self):
        self.approve()
        self.issue()
        self.verify()

        with self.assertRaises(ValidationError):
            self.verify()

        self.assertEqual(
            ContractorPaymentSettlementVerification.objects.filter(
                payment_record=self.payment
            ).count(),
            1,
        )