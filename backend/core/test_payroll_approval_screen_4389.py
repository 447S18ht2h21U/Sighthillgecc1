"""Five database-free checks of the fictional Approvals adapter."""

from copy import deepcopy
from unittest import TestCase

from payroll_approval_screen_4389 import (
    format_fictional_approval_screen_4389 as format_screen,
    approval_screen_4389_grants_live_access,
)


def row(workstream="SALES", stage="WAITING_MANAGER"):
    data = {
        "reference": "TEST-001",
        "recipient": "Fictional Contractor",
        "workstream": workstream,
        "amount": "1250.00",
        "requester_id": "TEST-REQUESTER",
        "recipient_id": "TEST-RECIPIENT",
        "first_approver_id": None,
        "first_approver_role": None,
        "first_audit_reference": None,
        "final_approver_id": None,
        "final_approver_role": None,
        "final_audit_reference": None,
        "stage": stage,
        "audit_evidence": "PENDING",
        "actual_paid_date": None,
        "actual_paid_date_verified": False,
    }

    if stage != "WAITING_MANAGER":
        data.update({
            "first_approver_id": "TEST-MANAGER",
            "first_approver_role": (
                "SALES_MANAGER" if workstream == "SALES"
                else "INSTALLATION_MANAGER"
            ),
            "first_audit_reference": "TEST-AUDIT-MANAGER",
        })

    if stage == "APPROVED":
        data.update({
            "final_approver_id": "TEST-COMPTROLLER",
            "final_approver_role": "COMPTROLLER",
            "final_audit_reference": "TEST-AUDIT-FINAL",
            "audit_evidence": "RECORDED",
        })

    return data


def fixture():
    return {
        "view": "fictional_approvals_review_only",
        "manager_authority_verified": False,
        "comptroller_authority_verified": False,
        "live_approval_authorized": False,
        "payment_actions_authorized": False,
        "actual_paid_date_verified": False,
        "rows": [row()],
    }


class ApprovalScreen4389Tests(TestCase):

    def test_01_manager_pending_maps_without_authority(self):
        result = format_screen(fixture())
        self.assertEqual(result["rows"][0]["stage"], "WAITING_MANAGER")
        self.assertFalse(result["live_approval_authorized"])

    def test_02_all_stages_and_both_workstreams(self):
        for workstream in ("SALES", "INSTALLATION"):
            for stage in (
                "WAITING_MANAGER",
                "WAITING_COMPTROLLER",
                "APPROVED",
            ):
                data = fixture()
                data["rows"] = [row(workstream, stage)]
                result = format_screen(data)
                self.assertEqual(result["rows"][0]["stage"], stage)
                self.assertEqual(
                    result["rows"][0]["workstream"], workstream
                )

    def test_03_self_approval_and_invalid_audit_rejected(self):
        data = fixture()
        data["rows"] = [row("SALES", "APPROVED")]
        data["rows"][0]["final_approver_id"] = "TEST-REQUESTER"
        with self.assertRaises(ValueError):
            format_screen(data)

        data["rows"][0]["final_approver_id"] = "TEST-COMPTROLLER"
        data["rows"][0]["final_audit_reference"] = None
        with self.assertRaises(ValueError):
            format_screen(data)

    def test_04_duplicate_real_and_unsafe_data_rejected(self):
        data = fixture()
        data["rows"].append(deepcopy(data["rows"][0]))
        with self.assertRaises(ValueError):
            format_screen(data)

        data = fixture()
        data["rows"][0]["reference"] = "REAL-001"
        with self.assertRaises(ValueError):
            format_screen(data)

        data = fixture()
        data["rows"][0]["actual_paid_date"] = "2026-11-11"
        with self.assertRaises(ValueError):
            format_screen(data)

        data = fixture()
        data["manager_authority_verified"] = True
        with self.assertRaises(ValueError):
            format_screen(data)

    def test_05_allowlist_and_non_authorization(self):
        data = fixture()
        data["bank_account"] = "SECRET-DO-NOT-EXPOSE"
        data["rows"][0]["tax_identifier"] = "SECRET-DO-NOT-EXPOSE"
        before = deepcopy(data)

        result = format_screen(data)

        self.assertEqual(data, before)
        self.assertNotIn("SECRET-DO-NOT-EXPOSE", str(result))
        self.assertFalse(result["payment_actions_authorized"])
        self.assertFalse(result["comptroller_authority_verified"])
        self.assertFalse(approval_screen_4389_grants_live_access())
