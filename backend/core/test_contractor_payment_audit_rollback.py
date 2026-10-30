"""Transactional rollback tests for contractor payment audit failures."""

from unittest.mock import patch

from django.test import TestCase

from .contractor_payment_services import mark_contractor_payment_paid
from .contractor_payment_issuance_services import issue_contractor_payment
from .contractor_payment_settlement_services import (
    verify_contractor_payment_settlement,
)
from .models import (
    AuditEvent,
    ContractorPaymentIssuance,
    ContractorPaymentRecord,
    ContractorPaymentSettlementVerification,
)
from .test_contractor_payment_four_stage import (
    ContractorPaymentFourStageTests,
)


class ContractorPaymentAuditRollbackTests(TestCase):
    """Every financial evidence write must roll back with its failed audit."""

    def setUp(self):
        ContractorPaymentFourStageTests.setUp(self)

    def approve_payment(self):
        return ContractorPaymentFourStageTests.approve(self)

    def issue_payment(self):
        return ContractorPaymentFourStageTests.issue(self)

    def verify_settlement(self):
        return ContractorPaymentFourStageTests.verify(self)

    def test_issuance_rolls_back_when_audit_fails(self):
        self.approve_payment()
        original_count = AuditEvent.objects.count()

        with patch(
            "core.contractor_payment_issuance_services.audit",
            side_effect=RuntimeError("Simulated issuance audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated issuance"):
                self.issue_payment()

        self.assertFalse(
            ContractorPaymentIssuance.objects.filter(
                payment_record=self.payment
            ).exists()
        )
        self.assertEqual(AuditEvent.objects.count(), original_count)
        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

    def test_settlement_rolls_back_when_audit_fails(self):
        self.approve_payment()
        issuance = self.issue_payment()
        original_count = AuditEvent.objects.count()

        with patch(
            "core.contractor_payment_settlement_services.audit",
            side_effect=RuntimeError("Simulated settlement audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated settlement"):
                self.verify_settlement()

        self.assertFalse(
            ContractorPaymentSettlementVerification.objects.filter(
                payment_record=self.payment
            ).exists()
        )
        self.assertTrue(
            ContractorPaymentIssuance.objects.filter(pk=issuance.pk).exists()
        )
        self.assertEqual(AuditEvent.objects.count(), original_count)
        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

    def test_paid_transition_rolls_back_when_audit_fails(self):
        self.approve_payment()
        issuance = self.issue_payment()
        verification = self.verify_settlement()
        original_count = AuditEvent.objects.count()

        with patch(
            "core.contractor_payment_services.audit",
            side_effect=RuntimeError("Simulated payment audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Simulated payment"):
                mark_contractor_payment_paid(
                    self.comptroller, self.payment.pk
                )

        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status,
            ContractorPaymentRecord.Status.APPROVED,
        )
        self.assertIsNone(self.payment.paid_at)
        self.assertEqual(AuditEvent.objects.count(), original_count)
        self.assertTrue(
            ContractorPaymentIssuance.objects.filter(pk=issuance.pk).exists()
        )
        self.assertTrue(
            ContractorPaymentSettlementVerification.objects.filter(
                pk=verification.pk
            ).exists()
        )