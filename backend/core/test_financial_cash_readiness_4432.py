"""Database-backed regression for Step 4432 cash readiness."""

from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import test_customer_payment_bank_confirmation as customer_fixture
from . import test_contractor_payment_four_stage as contractor_fixture
from .financial_cash_readiness_4432 import (
    preview_financial_cash_readiness_4432 as preview,
)


class CustomerCashReadiness4432Tests(TestCase):
    setUp = customer_fixture.CustomerPaymentBankConfirmationTests.setUp
    verify = customer_fixture.CustomerPaymentBankConfirmationTests.verify
    confirm = customer_fixture.CustomerPaymentBankConfirmationTests.confirm

    def test_01_verified_unconfirmed_receipt_is_listed(self):
        self.verify()
        day = timezone.localdate()
        result = preview(day, day)
        kinds = [item["kind"] for item in result["exceptions"]]
        self.assertIn("CUSTOMER_VERIFIED_BANK_UNCONFIRMED", kinds)
        self.assertEqual(
            result["partial_cash"]["supported_receipts"], "0.00"
        )
        self.assertFalse(result["financial_statement_ready"])

    def test_02_bank_confirmation_supports_partial_receipt(self):
        self.verify()
        self.confirm()
        day = timezone.localdate()
        result = preview(day, day)
        self.assertEqual(
            result["partial_cash"]["supported_receipts"], "5000.00"
        )
        self.assertEqual(result["exception_count"], 0)
        self.assertFalse(result["financial_statement_certified"])


class ContractorCashReadiness4432Tests(TestCase):
    setUp = contractor_fixture.ContractorPaymentFourStageTests.setUp
    approve = contractor_fixture.ContractorPaymentFourStageTests.approve
    issue = contractor_fixture.ContractorPaymentFourStageTests.issue
    verify = contractor_fixture.ContractorPaymentFourStageTests.verify

    def test_03_approved_not_issued_is_visible(self):
        self.approve()
        result = preview(date(2026, 10, 15), date(2026, 10, 15))
        kinds = [item["kind"] for item in result["exceptions"]]
        self.assertIn("CONTRACTOR_APPROVED_NOT_ISSUED", kinds)
        self.assertFalse(result["bank_reconciled"])

    def test_04_issued_not_settled_is_visible(self):
        self.approve()
        self.issue()
        result = preview(date(2026, 10, 15), date(2026, 10, 15))
        kinds = [item["kind"] for item in result["exceptions"]]
        self.assertIn("CONTRACTOR_ISSUED_NOT_SETTLED", kinds)

    def test_05_settled_not_paid_remains_visible(self):
        self.approve()
        self.issue()
        self.verify()
        result = preview(date(2026, 10, 15), date(2026, 10, 15))
        kinds = [item["kind"] for item in result["exceptions"]]
        self.assertIn("CONTRACTOR_VERIFIED_NOT_MARKED_PAID", kinds)


class EmptyCashReadiness4432Tests(TestCase):
    def test_06_read_only_and_not_ready(self):
        day = timezone.localdate()
        with CaptureQueriesContext(connection) as captured:
            result = preview(day, day)

        self.assertEqual(result["exception_count"], 0)
        self.assertFalse(result["inventory_complete"])
        self.assertFalse(result["financial_statement_ready"])
        self.assertFalse(result["bank_reconciled"])
        self.assertGreater(len(captured), 0)
        for item in captured:
            self.assertTrue(
                item["sql"].lstrip().upper().startswith("SELECT"),
                item["sql"],
            )
