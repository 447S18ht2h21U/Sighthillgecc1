from datetime import date
from unittest import TestCase
from financial_cash_evidence_4419 import cash_evidence_review_4419 as review

START = date(2026, 10, 1)
END = date(2026, 10, 31)

def record(ref, kind, amount, **extra):
    return dict(
        reference="TEST-" + ref, kind=kind, amount=amount,
        date=date(2026, 10, 15), **extra
    )

class CashEvidence4419Tests(TestCase):
    def test_01_confirmed_customer_receipt(self):
        result = review([record(
            "RECEIPT", "CUSTOMER_RECEIPT", "1000.00",
            customer_status="VERIFIED", bank_confirmed=True,
            independently_verified=True
        )], START, END)
        self.assertEqual(result["supported_test_cash_flow"], "1000.00")
        self.assertFalse(result["bank_reconciled"])

    def test_02_verified_contractor_settlement(self):
        result = review([record(
            "CONTRACTOR", "CONTRACTOR_SETTLEMENT", "400.00",
            payment_status="PAID", settlement_verified=True,
            independently_verified=True
        )], START, END)
        self.assertEqual(result["supported_test_cash_flow"], "-400.00")

    def test_03_unverified_receipts_and_settlements_withheld(self):
        items = [
            record("R", "CUSTOMER_RECEIPT", "1000.00",
                   customer_status="VERIFIED", bank_confirmed=False),
            record("C", "CONTRACTOR_SETTLEMENT", "400.00",
                   payment_status="PAID", settlement_verified=False)
        ]
        result = review(items, START, END)
        self.assertEqual(result["supported_test_cash_flow"], "0.00")
        self.assertEqual(len(result["withheld"]), 2)

    def test_04_issuance_adjustment_and_commission_excluded(self):
        items = [
            record("E", "EMPLOYEE_ISSUANCE", "300.00"),
            record("A", "CUSTOMER_ADJUSTMENT", "200.00"),
            record("M", "APPROVED_COMMISSION", "100.00")
        ]
        result = review(items, START, END)
        self.assertEqual(result["supported_test_cash_flow"], "0.00")
        self.assertEqual(len(result["withheld"]), 3)

    def test_05_period_and_duplicate_guards(self):
        a = record("R", "CUSTOMER_RECEIPT", "100.00",
                   customer_status="VERIFIED", bank_confirmed=True,
                   independently_verified=True)
        with self.assertRaises(ValueError):
            review([a, a], START, END)
        outside = dict(a, date=date(2026, 9, 30))
        result = review([outside], START, END)
        self.assertEqual(result["supported_test_cash_flow"], "0.00")
        self.assertEqual(len(result["withheld"]), 1)

    def test_06_reconcile_evidence_without_certification(self):
        items = [
            record("R", "CUSTOMER_RECEIPT", "1000.00",
                   customer_status="VERIFIED", bank_confirmed=True,
                   independently_verified=True),
            record("C", "CONTRACTOR_SETTLEMENT", "400.00",
                   payment_status="PAID", settlement_verified=True,
                   independently_verified=True),
        ]
        result = review(items, START, END)
        self.assertEqual(result["supported_test_cash_flow"], "600.00")
        self.assertEqual(len(result["included_references"]), 2)
        self.assertFalse(result["financial_statement_certified"])
        self.assertFalse(result["operational_records_accessed"])
