"""Isolated tests for refund and payroll evidence exceptions."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import test_customer_payment_bank_confirmation as existing
from .financial_cash_exceptions_4428 import (
    payroll_exception_4428,
    preview_cash_exceptions_4428,
    refund_exception_4428,
)
from .models import CustomerPaymentAdjustment
from .payment_services import approve_customer_payment_adjustment


class CashExceptionDecisions4428Tests(SimpleTestCase):
    def test_01_approved_refund_never_claims_settlement(self):
        item = SimpleNamespace(
            pk="TEST-REFUND",
            status=CustomerPaymentAdjustment.Status.APPROVED,
            amount=Decimal("100.00"),
            adjustment_date=date(2026, 10, 15),
        )
        result = refund_exception_4428(item)
        self.assertFalse(result["cash_settlement_verified"])
        self.assertEqual(
            result["review_date_type"],
            "ADJUSTMENT_DATE_NOT_SETTLEMENT",
        )

    def test_02_pending_refund_not_misclassified(self):
        item = SimpleNamespace(
            pk="TEST-PENDING",
            status=CustomerPaymentAdjustment.Status.PENDING,
            amount=Decimal("100.00"),
            adjustment_date=date(2026, 10, 15),
        )
        self.assertIsNone(refund_exception_4428(item))

    def test_03_paid_payroll_is_not_bank_settlement(self):
        item = SimpleNamespace(
            pk="TEST-PAYROLL",
            status="PAID",
            net_amount=Decimal("300.00"),
            paid_at=timezone.now(),
        )
        result = payroll_exception_4428(item)
        self.assertFalse(result["cash_settlement_verified"])
        self.assertEqual(
            result["review_date_type"],
            "PAID_STATUS_DATE_NOT_SETTLEMENT",
        )

    def test_04_missing_payroll_timestamp_explicit(self):
        item = SimpleNamespace(
            pk="TEST-NO-DATE",
            status="PAID",
            net_amount=Decimal("300.00"),
            paid_at=None,
        )
        result = payroll_exception_4428(item)
        self.assertIsNone(result["review_date"])
        self.assertEqual(
            result["review_date_type"],
            "MISSING_PAID_TIMESTAMP",
        )


class CashExceptionPopulated4428Tests(TestCase):
    setUp = existing.CustomerPaymentBankConfirmationTests.setUp
    verify = existing.CustomerPaymentBankConfirmationTests.verify

    def test_05_approved_refund_record_requires_cash_evidence(self):
        self.verify()
        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=self.payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("1000.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="4428-SYNTHETIC-REFUND",
            reason="Isolated refund evidence test",
            recorded_by=self.comptroller,
        )
        approve_customer_payment_adjustment(
            self.comptroller, adjustment.pk
        )

        today = timezone.localdate()
        result = preview_cash_exceptions_4428(today, today)

        self.assertEqual(result["exception_count"], 1)
        self.assertFalse(result["bank_reconciled"])
        self.assertFalse(result["cash_flow_complete"])
        self.assertFalse(result["financial_statement_certified"])
        self.assertEqual(
            result["exceptions"][0]["record_id"], str(adjustment.pk)
        )


class CashExceptionEmpty4428Tests(TestCase):
    def test_06_empty_database_queries_are_read_only(self):
        today = timezone.localdate()

        with CaptureQueriesContext(connection) as captured:
            result = preview_cash_exceptions_4428(today, today)

        self.assertEqual(result["exception_count"], 0)
        self.assertFalse(result["financial_statement_certified"])
        self.assertGreater(len(captured), 0)
        for query in captured:
            self.assertTrue(
                query["sql"].lstrip().upper().startswith("SELECT"),
                query["sql"],
            )
