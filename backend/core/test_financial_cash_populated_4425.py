"""4425: populated disposable-DB tests for read-only cash evidence."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from . import test_customer_payment_bank_confirmation as customer_fixtures
from . import test_contractor_payment_four_stage as contractor_fixtures
from .financial_cash_adapter_4422 import preview_cash_evidence_4422
from .models import CustomerPaymentAdjustment, ContractorPaymentRecord
from .payment_services import approve_customer_payment_adjustment
from .contractor_payment_services import mark_contractor_payment_paid


def today_period():
    day = timezone.localdate()
    return day, day


class CustomerCashPopulated4425Tests(TestCase):
    setUp = customer_fixtures.CustomerPaymentBankConfirmationTests.setUp
    verify = customer_fixtures.CustomerPaymentBankConfirmationTests.verify
    confirm = customer_fixtures.CustomerPaymentBankConfirmationTests.confirm

    def test_01_verified_bank_confirmed_receipt_included(self):
        self.verify()
        self.confirm()
        result = preview_cash_evidence_4422(*today_period())
        self.assertEqual(result["supported_receipts"], "5000.00")
        self.assertEqual(result["counted_evidence_records"], 1)
        self.assertFalse(result["financial_statement_certified"])

    def test_02_unconfirmed_payment_not_counted(self):
        self.verify()
        result = preview_cash_evidence_4422(*today_period())
        self.assertEqual(result["supported_receipts"], "0.00")
        self.assertEqual(result["counted_evidence_records"], 0)
        self.assertFalse(result["scope_complete"])

    def test_03_approved_refund_requires_separate_review(self):
        self.verify()
        self.confirm()
        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=self.payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("1000.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="4425-TEST-PARTIAL-REFUND",
            reason="Fictional cash reconciliation adjustment",
            recorded_by=self.comptroller,
        )
        approve_customer_payment_adjustment(
            self.comptroller, adjustment.pk
        )
        result = preview_cash_evidence_4422(*today_period())
        self.assertEqual(result["supported_receipts"], "0.00")
        self.assertEqual(len(result["withheld_evidence"]), 1)
        self.assertIn(
            "adjustment",
            result["withheld_evidence"][0]["reason"].lower()
        )

    def test_04_customer_confirmation_period_boundary(self):
        self.verify()
        self.confirm()
        tomorrow = timezone.localdate() + timedelta(days=1)
        result = preview_cash_evidence_4422(tomorrow, tomorrow)
        self.assertEqual(result["supported_receipts"], "0.00")
        self.assertEqual(result["counted_evidence_records"], 0)


class ContractorCashPopulated4425Tests(TestCase):
    setUp = contractor_fixtures.ContractorPaymentFourStageTests.setUp
    approve = contractor_fixtures.ContractorPaymentFourStageTests.approve
    issue = contractor_fixtures.ContractorPaymentFourStageTests.issue
    verify = contractor_fixtures.ContractorPaymentFourStageTests.verify

    def test_05_independent_settlement_requires_paid_state(self):
        self.approve()
        self.issue()
        self.verify()

        before = preview_cash_evidence_4422(*today_period())
        self.assertEqual(
            before["supported_contractor_disbursements"], "0.00"
        )
        self.assertEqual(len(before["withheld_evidence"]), 1)

        mark_contractor_payment_paid(self.comptroller, self.payment.pk)
        self.payment.refresh_from_db()
        self.assertEqual(
            self.payment.status, ContractorPaymentRecord.Status.PAID
        )

        after = preview_cash_evidence_4422(*today_period())
        self.assertEqual(
            after["supported_contractor_disbursements"], "125.00"
        )
        self.assertEqual(after["partial_net_cash_movement"], "-125.00")
        self.assertEqual(after["counted_evidence_records"], 1)

    def test_06_contractor_settlement_period_boundary(self):
        self.approve()
        self.issue()
        self.verify()
        mark_contractor_payment_paid(self.comptroller, self.payment.pk)

        tomorrow = timezone.localdate() + timedelta(days=1)
        result = preview_cash_evidence_4422(tomorrow, tomorrow)
        self.assertEqual(
            result["supported_contractor_disbursements"], "0.00"
        )
        self.assertEqual(result["counted_evidence_records"], 0)
        self.assertFalse(result["bank_reconciled"])
