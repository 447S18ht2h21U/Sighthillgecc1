"""Disposable SQLite historical full-customer-payment candidate tests."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from . import test_customer_payments as payment_fixtures
from .models import (
    AuditEvent,
    AuditHead,
    CustomerPayment,
    CustomerPaymentAdjustment,
    Outbox,
)
from .payment_services import (
    verify_customer_payment,
    approve_customer_payment_adjustment,
)
from .customer_payment_bank_confirmation_services import (
    confirm_customer_payment_bank_availability,
)
from .payroll_customer_earning_evidence_4303 import (
    candidate_full_customer_receipt_date,
    customer_earning_candidate_grants_live_access,
)


class CustomerEarningEvidence4303Tests(TestCase):
    setUp = payment_fixtures.CustomerPaymentVerificationTests.setUp

    def confirm(self, payment, reference):
        return confirm_customer_payment_bank_availability(
            actor=self.comptroller,
            payment_id=payment.pk,
            bank_reference=reference,
            confirmation_date=timezone.localdate(),
            confirmation_method="Test-only bank review",
            confirmation_note="Verified available funds in disposable database.",
        )

    def verify_and_confirm(self, payment, reference):
        verify_customer_payment(self.comptroller, payment.pk)
        self.confirm(payment, reference)

    def final_payment(self, amount=Decimal("500.00")):
        return CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FINAL,
            amount=amount,
            received_date=date(2026, 10, 15),
            payment_reference="EARN-4303-FINAL",
            recorded_by=self.sales_manager,
        )

    def candidate(self):
        return candidate_full_customer_receipt_date(
            project_id=self.project.pk
        )

    def test_unverified_deposit_does_not_establish_date(self):
        self.assertIsNone(self.candidate())

    def test_bank_confirmed_deposit_is_not_full_payment(self):
        self.verify_and_confirm(self.payment, "BANK-4303-DEP")
        self.assertIsNone(self.candidate())

    def test_two_verified_confirmed_receipts_establish_candidate(self):
        self.verify_and_confirm(self.payment, "BANK-4303-DEP")
        final = self.final_payment()
        self.verify_and_confirm(final, "BANK-4303-FINAL")
        self.assertEqual(self.candidate(), date(2026, 10, 15))
        self.assertFalse(customer_earning_candidate_grants_live_access())

    def test_pending_final_payment_does_not_establish_date(self):
        self.verify_and_confirm(self.payment, "BANK-4303-DEP")
        self.final_payment()
        self.assertIsNone(self.candidate())

    def test_verified_final_without_bank_confirmation_denied(self):
        self.verify_and_confirm(self.payment, "BANK-4303-DEP")
        final = self.final_payment()
        verify_customer_payment(self.comptroller, final.pk)
        self.assertIsNone(self.candidate())

    def test_approved_refund_requires_separate_historical_review(self):
        self.verify_and_confirm(self.payment, "BANK-4303-DEP")
        final = self.final_payment()
        self.verify_and_confirm(final, "BANK-4303-FINAL")

        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=self.payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("50.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="REFUND-4303",
            reason="Test-only historical adjustment",
            recorded_by=self.comptroller,
        )
        approve_customer_payment_adjustment(
            self.comptroller, adjustment.pk
        )
        self.assertIsNone(self.candidate())

    def test_candidate_read_is_nonmutating(self):
        self.verify_and_confirm(self.payment, "BANK-4303-DEP")
        final = self.final_payment()
        self.verify_and_confirm(final, "BANK-4303-FINAL")

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                AuditEvent.objects.count(),
                Outbox.objects.count(),
                list(CustomerPayment.objects.filter(
                    project=self.project
                ).order_by("pk").values_list(
                    "pk", "status", "verified_at"
                )),
            )

        before = state()
        self.assertEqual(self.candidate(), date(2026, 10, 15))
        self.assertEqual(state(), before)