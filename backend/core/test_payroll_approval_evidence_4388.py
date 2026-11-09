"""Seven focused, database-free checks of fictional approval evidence."""

from copy import deepcopy
from unittest import TestCase

from payroll_approval_evidence_4388 import (
    validate_fictional_approval_evidence_4388 as validate,
    approval_evidence_4388_grants_live_access,
)


def fixture():
    return {
        "view": "fictional_approvals_review_only",
        "workstream": "SALES",
        "stage": "WAITING_MANAGER",
        "requester_id": "TEST-REQUESTER",
        "recipient_id": "TEST-RECIPIENT",
        "first_approver_id": None,
        "first_approver_role": None,
        "first_audit_reference": None,
        "final_approver_id": None,
        "final_approver_role": None,
        "final_audit_reference": None,
        "manager_authority_verified": False,
        "comptroller_authority_verified": False,
        "live_approval_authorized": False,
        "payment_actions_authorized": False,
        "actual_paid_date_verified": False,
        "actual_paid_date": None,
    }


def manager_review(data):
    data["stage"] = "WAITING_COMPTROLLER"
    data["first_approver_id"] = "TEST-MANAGER"
    data["first_approver_role"] = "SALES_MANAGER"
    data["first_audit_reference"] = "TEST-AUDIT-MANAGER"


def final_review(data):
    manager_review(data)
    data["stage"] = "APPROVED"
    data["final_approver_id"] = "TEST-COMPTROLLER"
    data["final_approver_role"] = "COMPTROLLER"
    data["final_audit_reference"] = "TEST-AUDIT-FINAL"


class ApprovalEvidence4388Tests(TestCase):

    def test_01_manager_pending_has_no_approval(self):
        result = validate(fixture())
        self.assertEqual(result["stage"], "WAITING_MANAGER")
        self.assertFalse(result["liveApprovalAuthorized"])

    def test_02_manager_review_precedes_comptroller(self):
        data = fixture()
        manager_review(data)
        result = validate(data)
        self.assertEqual(result["stage"], "WAITING_COMPTROLLER")

        data["final_approver_id"] = "TEST-COMPTROLLER"
        with self.assertRaises(ValueError):
            validate(data)

    def test_03_distinct_comptroller_and_audits_required(self):
        data = fixture()
        final_review(data)
        self.assertEqual(validate(data)["stage"], "APPROVED")

        same_person = deepcopy(data)
        same_person["final_approver_id"] = "TEST-MANAGER"
        with self.assertRaises(ValueError):
            validate(same_person)

        same_audit = deepcopy(data)
        same_audit["final_audit_reference"] = "TEST-AUDIT-MANAGER"
        with self.assertRaises(ValueError):
            validate(same_audit)

    def test_04_requester_and_recipient_cannot_approve(self):
        for identity in ("TEST-REQUESTER", "TEST-RECIPIENT"):
            data = fixture()
            manager_review(data)
            data["first_approver_id"] = identity
            with self.assertRaises(ValueError):
                validate(data)

            data = fixture()
            final_review(data)
            data["final_approver_id"] = identity
            with self.assertRaises(ValueError):
                validate(data)

    def test_05_workstream_and_roles_must_match(self):
        data = fixture()
        manager_review(data)
        data["workstream"] = "INSTALLATION"
        with self.assertRaises(ValueError):
            validate(data)

        data["first_approver_role"] = "INSTALLATION_MANAGER"
        self.assertEqual(validate(data)["stage"], "WAITING_COMPTROLLER")

        final_review(data)
        data["final_approver_role"] = "CEO"
        with self.assertRaises(ValueError):
            validate(data)

    def test_06_unsafe_authority_and_dates_fail_closed(self):
        for key, value in (
            ("manager_authority_verified", True),
            ("comptroller_authority_verified", True),
            ("live_approval_authorized", True),
            ("payment_actions_authorized", True),
            ("actual_paid_date_verified", True),
            ("actual_paid_date", "2026-11-11"),
            ("requester_id", "REAL-123"),
        ):
            data = fixture()
            data[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    validate(data)

    def test_07_pure_output_never_authorizes(self):
        data = fixture()
        data["bank_account"] = "SECRET-DO-NOT-EXPOSE"
        original = deepcopy(data)
        result = validate(data)
        self.assertEqual(data, original)
        self.assertNotIn("SECRET-DO-NOT-EXPOSE", str(result))
        self.assertFalse(result["managerAuthorityVerified"])
        self.assertFalse(result["comptrollerAuthorityVerified"])
        self.assertFalse(result["paymentActionsAvailable"])
        self.assertFalse(approval_evidence_4388_grants_live_access())
