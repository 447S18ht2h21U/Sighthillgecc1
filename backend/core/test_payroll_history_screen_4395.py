"""Five isolated, database-free Payment History adapter tests."""

from copy import deepcopy
from unittest import TestCase

from payroll_history_screen_4395 import (
    format_fictional_payment_history_4395 as format_history,
    history_screen_4395_grants_live_access,
)


def fixture():
    return {
        "view": "fictional_payment_history_only",
        "backend_scope_verified": False,
        "external_payment_evidence_verified": False,
        "live_payment_authorized": False,
        "payment_actions_authorized": False,
        "rows": [{
            "reference": "TEST-ORIGINAL",
            "recipient": "Fictional Contractor",
            "category": "contractor",
            "kind": "COMPENSATION",
            "adjustment_of": None,
            "compensation_date": "2026-11-02",
            "period_start": "2026-11-02",
            "period_end": "2026-11-08",
            "amount": "1250.00",
            "recorded_status": "PAID",
            "proposed_payment_date": "2026-11-11",
            "issued_date": "2026-11-11",
            "settlement_candidate_date": "2026-11-12",
            "method": "ACH",
            "payment_reference": "TEST-ACH",
            "actual_paid_date": None,
            "actual_paid_date_verified": False,
            "exception": False,
            "bank_account": "SECRET-DO-NOT-EXPOSE",
        }],
    }


class PaymentHistoryScreen4395Tests(TestCase):

    def test_01_exact_amount_and_recorded_status(self):
        result = format_history(fixture())
        self.assertEqual(result["rows"][0]["amount"], "1250.00")
        self.assertEqual(result["rows"][0]["recorded_status"], "PAID")
        self.assertFalse(result["live_payment_authorized"])

    def test_02_issuance_is_not_actual_payment(self):
        result = format_history(fixture())["rows"][0]
        self.assertEqual(result["issued_date"], "2026-11-11")
        self.assertEqual(
            result["settlement_candidate_date"], "2026-11-12"
        )
        self.assertIsNone(result["actual_paid_date"])
        self.assertFalse(result["actual_paid_date_verified"])

    def test_03_adjustment_remains_separate(self):
        data = fixture()
        adjustment = deepcopy(data["rows"][0])
        adjustment.update({
            "reference": "TEST-ADJUSTMENT",
            "kind": "ADJUSTMENT",
            "adjustment_of": "TEST-ORIGINAL",
            "amount": "-50.00",
            "recorded_status": "APPROVED",
            "issued_date": None,
            "settlement_candidate_date": None,
            "method": None,
            "payment_reference": None,
            "exception": True,
        })
        data["rows"].append(adjustment)
        result = format_history(data)
        self.assertEqual(result["rows"][1]["amount"], "-50.00")
        self.assertEqual(
            result["rows"][1]["adjustment_of"], "TEST-ORIGINAL"
        )
        self.assertEqual(len(result["rows"]), 2)

    def test_04_unsafe_dates_scope_and_money_rejected(self):
        cases = (
            ("actual_paid_date", "2026-11-12"),
            ("actual_paid_date_verified", True),
            ("method", "WIRE"),
            ("amount", "-1250.00"),
            ("period_end", "2026-11-01"),
        )
        for key, value in cases:
            data = fixture()
            data["rows"][0][key] = value
            with self.subTest(field=key):
                with self.assertRaises(ValueError):
                    format_history(data)

        data = fixture()
        data["backend_scope_verified"] = True
        with self.assertRaises(ValueError):
            format_history(data)

        data = fixture()
        data["rows"].append(deepcopy(data["rows"][0]))
        with self.assertRaises(ValueError):
            format_history(data)

    def test_05_allowlist_and_no_live_authority(self):
        data = fixture()
        data["company_total"] = "SECRET-DO-NOT-EXPOSE"
        before = deepcopy(data)
        result = format_history(data)
        self.assertEqual(data, before)
        self.assertNotIn("SECRET-DO-NOT-EXPOSE", str(result))
        self.assertFalse(result["external_payment_evidence_verified"])
        self.assertFalse(result["payment_actions_authorized"])
        self.assertFalse(history_screen_4395_grants_live_access())
