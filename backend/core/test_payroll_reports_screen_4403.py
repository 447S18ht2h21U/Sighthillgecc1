"""Five database-free Payroll Reports presentation tests."""

from copy import deepcopy
from unittest import TestCase

from payroll_reports_screen_4403 import (
    format_fictional_payroll_reports_4403 as format_report,
    payroll_reports_4403_grants_live_access,
)


def obligation(**changes):
    result = {
        "reference": "TEST-COMP-A",
        "recipient": "Fictional Contractor Alpha",
        "category": "contractor",
        "kind": "COMPENSATION",
        "adjustment_of": None,
        "amount": "1250.00",
        "recorded_status": "PAID_RECORDED",
        "first_approval_recorded": True,
        "comptroller_approval_recorded": True,
        "audit_recorded": True,
        "independently_verified_paid_date": None,
        "independently_verified_paid": False,
        "exception": False,
    }
    result.update(changes)
    return result


def fixture():
    return {
        "view": "fictional_company_payroll_report_only",
        "period_start": "2026-11-02",
        "period_end": "2026-11-08",
        "backend_scope_verified": False,
        "external_payment_evidence_verified": False,
        "exports_available": False,
        "live_payroll_authorized": False,
        "rows": [
            obligation(),
            obligation(
                reference="TEST-COMP-B",
                recipient="Fictional Employee Beta",
                category="employee",
                amount="600.00",
                recorded_status="APPROVED",
            ),
            obligation(
                reference="TEST-ADJUST-A",
                kind="ADJUSTMENT",
                adjustment_of="TEST-COMP-A",
                amount="-50.00",
                recorded_status="DRAFT",
                first_approval_recorded=False,
                comptroller_approval_recorded=False,
                audit_recorded=False,
                exception=True,
            ),
        ],
    }


class PayrollReportsScreen4403Tests(TestCase):

    def test_01_exact_obligations_and_draft_adjustment(self):
        report = format_report(fixture())
        self.assertEqual(
            [row["amount"] for row in report["rows"]],
            ["1250.00", "600.00", "-50.00"]
        )
        self.assertEqual(report["rows"][2]["adjustment_of"], "TEST-COMP-A")
        self.assertEqual(report["rows"][2]["recorded_status"], "DRAFT")

    def test_02_recorded_paid_is_not_verified_paid(self):
        report = format_report(fixture())
        self.assertFalse(report["external_payment_evidence_verified"])
        self.assertFalse(report["rows"][0]["independently_verified_paid"])
        self.assertIsNone(
            report["rows"][0]["independently_verified_paid_date"]
        )
        data = fixture()
        data["rows"][0]["independently_verified_paid"] = True
        with self.assertRaises(ValueError):
            format_report(data)

    def test_03_period_and_approval_gates_fail_closed(self):
        for key, value in (
            ("period_start", "2026-11-03"),
            ("period_end", "2026-11-09"),
        ):
            data = fixture()
            data[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    format_report(data)

        data = fixture()
        data["rows"][0]["comptroller_approval_recorded"] = False
        with self.assertRaises(ValueError):
            format_report(data)

    def test_04_duplicate_and_invalid_adjustment_rejected(self):
        data = fixture()
        data["rows"].append(deepcopy(data["rows"][0]))
        with self.assertRaises(ValueError):
            format_report(data)

        data = fixture()
        data["rows"][2]["adjustment_of"] = "TEST-MISSING"
        with self.assertRaises(ValueError):
            format_report(data)

        data = fixture()
        data["rows"][2]["recorded_status"] = "APPROVED"
        with self.assertRaises(ValueError):
            format_report(data)

    def test_05_allowlist_privacy_and_no_live_access(self):
        data = fixture()
        data["rows"][0]["bank_account"] = "SECRET-DO-NOT-EXPOSE"
        data["tax_identifier"] = "SECRET-DO-NOT-EXPOSE"
        before = deepcopy(data)
        report = format_report(data)
        self.assertEqual(data, before)
        self.assertNotIn("SECRET-DO-NOT-EXPOSE", str(report))
        self.assertFalse(report["exports_available"])
        self.assertFalse(report["backend_scope_verified"])
        self.assertFalse(report["live_payroll_authorized"])
        self.assertFalse(payroll_reports_4403_grants_live_access())

        data = fixture()
        data["exports_available"] = True
        with self.assertRaises(ValueError):
            format_report(data)
