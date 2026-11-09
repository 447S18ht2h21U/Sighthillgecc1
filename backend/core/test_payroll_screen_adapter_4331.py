"""Isolated security checks for the approved payroll screen adapter."""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .payroll_screen_adapter_4331 import (
    candidate_personal_payroll_screen,
    format_authorized_personal_screen_candidate,
    payroll_screen_adapter_grants_live_access,
)


class PayrollScreenAdapter4331Tests(TestCase):
    def authorized(self):
        return {
            "view": "my_compensation",
            "period_start": "2026-11-02",
            "period_end": "2026-11-08",
            "amount_basis": "full_obligation_not_prorated",
            "employee_records": [{
                "period_start": "2026-11-02",
                "period_end": "2026-11-08",
                "compensation_type": "employee",
                "kind": "BASE",
                "amount": "600.00",
                "status": "APPROVED",
                "status_label": "Approved - Not Yet Paid",
                "payment_evidence_status": "NOT_ISSUED",
                "payment_issued_at": None,
                "scheduled_payment_date": None,
                "actual_paid_date": None,
                "bank_account": "SECRET-DO-NOT-EXPOSE",
            }],
            "contractor_records": [{
                "period_start": "2026-11-02",
                "period_end": "2026-11-08",
                "compensation_type": "contractor",
                "kind": "COMMISSION",
                "amount": "1250.00",
                "status": "PAID",
                "status_label": "Paid",
                "payment_evidence_status": "TEST_EVIDENCE",
                "payment_issued_at": "2026-11-11T10:00:00Z",
                "contractor_settlement_date": "2026-11-12",
                "scheduled_payment_date": None,
                "actual_paid_date": None,
                "tax_identifier": "SECRET-DO-NOT-EXPOSE",
            }],
            "account_number": "SECRET-DO-NOT-EXPOSE",
        }

    def test_existing_permission_gate_is_invoked_first(self):
        with patch(
            "core.payroll_screen_adapter_4331."
            "permitted_personal_payroll_presentation",
            return_value=self.authorized(),
        ) as gate:
            result = candidate_personal_payroll_screen(
                object(), "2026-11-02", "2026-11-08"
            )
        gate.assert_called_once()
        self.assertEqual(result["view"], "my_payroll_test_only")

    def test_denied_actor_does_not_receive_a_report(self):
        with patch(
            "core.payroll_screen_adapter_4331."
            "permitted_personal_payroll_presentation",
            side_effect=PermissionDenied("Not authorized"),
        ) as gate:
            with self.assertRaises(PermissionDenied):
                candidate_personal_payroll_screen(
                    None, "2026-11-02", "2026-11-08"
                )
        gate.assert_called_once()

    def test_allowlist_removes_private_identifiers(self):
        result = format_authorized_personal_screen_candidate(
            self.authorized()
        )
        self.assertNotIn("SECRET-DO-NOT-EXPOSE", str(result))
        self.assertNotIn("account_number", str(result))
        self.assertNotIn("bank_account", str(result))
        self.assertNotIn("tax_identifier", str(result))

    def test_issuance_and_settlement_are_not_actual_paid_dates(self):
        result = format_authorized_personal_screen_candidate(
            self.authorized()
        )
        contractor = result["contractor_records"][0]
        self.assertIsNone(contractor["actual_paid_date"])
        self.assertFalse(contractor["actual_paid_date_verified"])
        self.assertNotIn("payment_issued_at", contractor)
        self.assertNotIn("contractor_settlement_date", contractor)

    def test_approved_is_not_labeled_paid(self):
        result = format_authorized_personal_screen_candidate(
            self.authorized()
        )
        employee = result["employee_records"][0]
        self.assertEqual(employee["status"], "APPROVED")
        self.assertEqual(
            employee["status_label"], "Approved - Not Yet Paid"
        )

    def test_draft_and_unknown_statuses_denied(self):
        for status in ("DRAFT", "PENDING", "UNKNOWN", None):
            report = self.authorized()
            report["employee_records"][0]["status"] = status
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    format_authorized_personal_screen_candidate(report)

    def test_conflicting_status_label_denied(self):
        report = self.authorized()
        report["employee_records"][0]["status_label"] = "Paid"
        with self.assertRaises(ValueError):
            format_authorized_personal_screen_candidate(report)

    def test_invalid_amounts_and_dates_denied(self):
        for amount in ("-1.00", "1.234", "NaN", 500, "1,000.00"):
            report = self.authorized()
            report["employee_records"][0]["amount"] = amount
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    format_authorized_personal_screen_candidate(report)

        report = self.authorized()
        report["employee_records"][0]["period_end"] = "2026-10-01"
        with self.assertRaises(ValueError):
            format_authorized_personal_screen_candidate(report)

    def test_unverified_payment_date_and_extra_scope_denied(self):
        report = self.authorized()
        report["contractor_records"][0]["actual_paid_date"] = "2026-11-12"
        with self.assertRaises(ValueError):
            format_authorized_personal_screen_candidate(report)

        report = self.authorized()
        report["view"] = "company_payroll"
        with self.assertRaises(ValueError):
            format_authorized_personal_screen_candidate(report)

    def test_pure_formatting_is_nonmutating_and_non_authorizing(self):
        report = self.authorized()
        before = deepcopy(report)
        result = format_authorized_personal_screen_candidate(report)
        self.assertEqual(report, before)
        self.assertFalse(result["live_payroll_authorized"])
        self.assertFalse(result["manager_or_company_scope_authorized"])
        self.assertFalse(result["payment_actions_authorized"])
        self.assertFalse(payroll_screen_adapter_grants_live_access())