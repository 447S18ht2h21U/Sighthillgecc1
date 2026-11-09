"""Four focused synthetic accounting-readiness tests."""

from unittest import TestCase

from financial_readiness_4412 import (
    assess_balance_sheet_4412,
    assess_cash_flow_4412,
    assess_separate_review_4412,
)


class FinancialReadiness4412Tests(TestCase):

    def test_01_balanced_snapshot_does_not_claim_certification(self):
        result = assess_balance_sheet_4412({
            "assets": "9000.00",
            "liabilities": "3000.00",
            "equity": "6000.00",
        })
        self.assertTrue(result["arithmetically_balanced"])
        self.assertFalse(result["account_completeness_verified"])
        self.assertFalse(result["operationally_approved"])

    def test_02_missing_equity_or_unbalanced_report_fails(self):
        with self.assertRaises(ValueError):
            assess_balance_sheet_4412({
                "assets": "9000.00",
                "liabilities": "3000.00",
            })
        with self.assertRaises(ValueError):
            assess_balance_sheet_4412({
                "assets": "9000.00",
                "liabilities": "3000.00",
                "equity": "5000.00",
            })

    def test_03_verified_cash_movements_reconcile(self):
        data = {
            "reported_net_cash_flow": "600.00",
            "movements": [
                {
                    "reference": "TEST-RECEIPT",
                    "kind": "RECEIPT",
                    "amount": "1000.00",
                    "independently_verified": True,
                },
                {
                    "reference": "TEST-DISBURSEMENT",
                    "kind": "DISBURSEMENT",
                    "amount": "400.00",
                    "independently_verified": True,
                },
            ],
        }
        result = assess_cash_flow_4412(data)
        self.assertEqual(result["net_cash_flow"], "600.00")
        self.assertFalse(result["operationally_approved"])
        self.assertFalse(result["bank_reconciliation_verified"])

        data["movements"][1]["independently_verified"] = False
        with self.assertRaises(ValueError):
            assess_cash_flow_4412(data)

    def test_04_separate_reviewer_is_proposed_not_authorized(self):
        result = assess_separate_review_4412({
            "creator_id": "TEST-CREATOR",
            "reviewer_id": "TEST-REVIEWER",
        })
        self.assertTrue(result["different_reviewers"])
        self.assertFalse(
            result["corporate_approval_policy_confirmed"]
        )

        with self.assertRaises(ValueError):
            assess_separate_review_4412({
                "creator_id": "TEST-CREATOR",
                "reviewer_id": "TEST-CREATOR",
            })
