"""Focused Step 4422 cash evidence adapter regression."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .financial_cash_adapter_4422 import (
    preview_cash_evidence_4422,
    receipt_evidence_4422,
    settlement_evidence_4422,
)


def customer_fixture():
    now = timezone.now()
    payment = SimpleNamespace(
        pk=1,
        status="VERIFIED",
        amount=Decimal("1000.00"),
        verified_at=now - timedelta(days=1),
        verified_by_id=2,
        received_date=date(2026, 10, 10),
    )
    confirmation = SimpleNamespace(
        pk=10,
        payment=payment,
        bank_reference="TEST-BANK",
        confirmed_by_id=3,
        confirmed_at=now,
        confirmation_date=date(2026, 10, 11),
    )
    return confirmation


def contractor_fixture():
    now = timezone.now()
    payment = SimpleNamespace(
        pk=20,
        status="PAID",
        final_amount=Decimal("400.00"),
    )
    issuance = SimpleNamespace(
        payment_record_id=20,
        amount=Decimal("400.00"),
        issued_by_id=4,
        issued_at=now - timedelta(days=2),
    )
    return SimpleNamespace(
        pk=30,
        payment_record=payment,
        payment_record_id=20,
        issuance=issuance,
        cleared_amount=Decimal("400.00"),
        verified_by_id=5,
        verified_at=now - timedelta(days=1),
        settlement_date=timezone.localdate(),
        evidence_reference="TEST-SETTLEMENT",
    )


class CashEvidenceDecision4422Tests(SimpleTestCase):

    def test_01_verified_customer_receipt(self):
        amount, reason = receipt_evidence_4422(
            customer_fixture(), False
        )
        self.assertEqual(amount, Decimal("1000.00"))
        self.assertIsNone(reason)

    def test_02_adjustment_or_missing_bank_confirmation_withheld(self):
        item = customer_fixture()
        self.assertIsNone(receipt_evidence_4422(item, True)[0])
        item.bank_reference = ""
        self.assertIsNone(receipt_evidence_4422(item, False)[0])

    def test_03_independent_contractor_settlement(self):
        amount, reason = settlement_evidence_4422(
            contractor_fixture()
        )
        self.assertEqual(amount, Decimal("400.00"))
        self.assertIsNone(reason)

    def test_04_mismatched_or_self_verified_settlement_withheld(self):
        item = contractor_fixture()
        item.cleared_amount = Decimal("300.00")
        self.assertIsNone(settlement_evidence_4422(item)[0])

        item = contractor_fixture()
        item.verified_by_id = item.issuance.issued_by_id
        self.assertIsNone(settlement_evidence_4422(item)[0])


class CashEvidenceDatabase4422Tests(TestCase):

    def test_05_empty_database_read_only_and_not_certified(self):
        with CaptureQueriesContext(connection) as captured:
            result = preview_cash_evidence_4422(
                date(2026, 10, 1),
                date(2026, 10, 31),
            )

        self.assertEqual(result["partial_net_cash_movement"], "0.00")
        self.assertEqual(result["counted_evidence_records"], 0)
        self.assertFalse(result["scope_complete"])
        self.assertFalse(result["bank_reconciled"])
        self.assertFalse(result["financial_statement_certified"])
        self.assertGreater(len(captured), 0)
        for item in captured:
            self.assertTrue(
                item["sql"].lstrip().upper().startswith("SELECT"),
                item["sql"],
            )
