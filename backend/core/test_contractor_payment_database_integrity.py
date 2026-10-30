"""SQLite contractor payment database integrity regression tests."""

from datetime import date
from decimal import Decimal

from django.db import DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone

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


class ContractorPaymentDatabaseIntegrityTests(TestCase):
    """Verify database safeguards independently of normal service updates."""

    def setUp(self):
        self.ceo = User.objects.create_user(
            username="db_integrity_ceo",
            role=Role.CEO,
        )
        self.comptroller = User.objects.create_user(
            username="db_integrity_comptroller",
            role=Role.COMPTROLLER,
        )

        contractor = Contractor.objects.create(
            contractor_number="CTR-DB-INTEGRITY",
            legal_name="Database Integrity Test Contractor",
            created_by=self.comptroller,
        )

        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code="ENG-DB-INTEGRITY",
            role_description="Database integrity testing",
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )

        plan = ContractorCompensationPlan.objects.create(
            engagement=engagement,
            version=1,
            effective_date=date(2026, 10, 1),
            compensation_terms={"amount": "125.00"},
            status=ContractorCompensationPlan.Status.APPROVED,
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )

        self.payment = create_contractor_payment_record(
            self.comptroller,
            engagement,
            plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal("125.00"),
            Decimal("0.00"),
            Decimal("125.00"),
            {"source": "DATABASE_INTEGRITY_TEST"},
        )

    def approve(self):
        approve_contractor_payment_record(
            self.ceo,
            self.payment.pk,
        )

    def issue(self):
        return issue_contractor_payment(
            self.ceo,
            self.payment.pk,
            Decimal("125.00"),
            "ACH",
            "DATABASE-INTEGRITY-ISSUANCE",
            "Test-only issuance evidence",
        )

    def verify(self):
        return verify_contractor_payment_settlement(
            self.comptroller,
            self.payment.pk,
            timezone.localdate(),
            Decimal("125.00"),
            "DATABASE-INTEGRITY-SETTLEMENT",
        )

    def assert_database_rejects(self, operation):
        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                operation()

    def test_issuance_cannot_be_modified(self):
        self.approve()
        issuance = self.issue()

        self.assert_database_rejects(
            lambda: ContractorPaymentIssuance.objects.filter(
                pk=issuance.pk
            ).update(amount=Decimal("999.00"))
        )

    def test_issuance_cannot_be_deleted(self):
        self.approve()
        issuance = self.issue()

        self.assert_database_rejects(
            lambda: ContractorPaymentIssuance.objects.filter(
                pk=issuance.pk
            ).delete()
        )

    def test_settlement_cannot_be_modified(self):
        self.approve()
        self.issue()
        settlement = self.verify()

        self.assert_database_rejects(
            lambda: ContractorPaymentSettlementVerification.objects.filter(
                pk=settlement.pk
            ).update(cleared_amount=Decimal("999.00"))
        )

    def test_settlement_cannot_be_deleted(self):
        self.approve()
        self.issue()
        settlement = self.verify()

        self.assert_database_rejects(
            lambda: ContractorPaymentSettlementVerification.objects.filter(
                pk=settlement.pk
            ).delete()
        )

    def test_paid_transition_without_evidence_is_rejected(self):
        self.approve()

        self.assert_database_rejects(
            lambda: ContractorPaymentRecord.objects.filter(
                pk=self.payment.pk
            ).update(
                status=ContractorPaymentRecord.Status.PAID,
                paid_at=timezone.now(),
            )
        )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

    def test_historical_evidence_survives_role_changes(self):
        self.approve()
        issuance = self.issue()
        settlement = self.verify()

        User.objects.filter(pk=self.ceo.pk).update(
            role=Role.TECHNICIAN,
            is_active=False,
        )
        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.TECHNICIAN,
            is_active=False,
        )

        self.assertTrue(
            ContractorPaymentIssuance.objects.filter(
                pk=issuance.pk
            ).exists()
        )
        self.assertTrue(
            ContractorPaymentSettlementVerification.objects.filter(
                pk=settlement.pk
            ).exists()
        )

        ContractorPaymentRecord.objects.filter(
            pk=self.payment.pk
        ).update(
            status=ContractorPaymentRecord.Status.PAID,
            paid_at=timezone.now(),
        )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.PAID,
        )

    def test_valid_payment_completion_preserves_evidence(self):
        self.approve()
        issuance = self.issue()
        settlement = self.verify()

        mark_contractor_payment_paid(
            self.comptroller,
            self.payment.pk,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.PAID,
        )
        self.assertEqual(issuance.issued_by_id, self.ceo.pk)
        self.assertEqual(
            settlement.verified_by_id,
            self.comptroller.pk,
        )