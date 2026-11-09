"""Four focused tests for approved corporate approval policy."""

from copy import deepcopy
from unittest import TestCase

from financial_approval_policy_4413 import (
    evaluate_financial_approval_4413 as review,
    fingerprint_draft_4413,
    approval_policy_grants_live_access_4413,
)


def fixture():
    return {
        "creator_role": "COMPTROLLER",
        "approver_role": "CEO",
        "creator_id": "TEST-COMPTROLLER",
        "approver_id": "TEST-CEO",
        "report_status": "DRAFT",
        "accounting_reconciled": True,
        "evidence_verified": True,
        "report_snapshot": {
            "assets": "9000.00",
            "liabilities": "3000.00",
            "equity": "6000.00",
        },
    }


class FinancialApprovalPolicy4413Tests(TestCase):

    def test_01_comptroller_and_distinct_ceo_required(self):
        result = review(fixture())
        self.assertEqual(
            result["policy"], "COMPTROLLER_PREPARES_CEO_APPROVES"
        )
        self.assertTrue(result["policy_conditions_satisfied"])
        self.assertFalse(result["operational_approval_performed"])

    def test_02_wrong_roles_and_self_approval_rejected(self):
        for field, value in (
            ("creator_role", "SALES_MANAGER"),
            ("approver_role", "COMPTROLLER"),
            ("approver_id", "TEST-COMPTROLLER"),
            ("report_status", "APPROVED"),
        ):
            data = fixture()
            data[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    review(data)

    def test_03_missing_reconciliation_or_evidence_rejected(self):
        for field in ("accounting_reconciled", "evidence_verified"):
            data = fixture()
            data[field] = False
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    review(data)

        data = fixture()
        data["report_snapshot"] = {}
        with self.assertRaises(ValueError):
            review(data)

    def test_04_snapshot_fingerprint_and_audit_boundary(self):
        original = fixture()
        before = deepcopy(original)
        result = review(original)
        self.assertEqual(original, before)
        self.assertEqual(
            result["snapshot_sha256"],
            fingerprint_draft_4413(original["report_snapshot"])
        )

        changed = fixture()
        changed["report_snapshot"]["equity"] = "5000.00"
        self.assertNotEqual(
            result["snapshot_sha256"],
            fingerprint_draft_4413(changed["report_snapshot"])
        )

        self.assertFalse(result["durable_audit_written"])
        self.assertFalse(result["database_immutability_verified"])
        self.assertFalse(approval_policy_grants_live_access_4413())
