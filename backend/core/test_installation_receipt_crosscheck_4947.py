from unittest import TestCase
from django.core.exceptions import ValidationError

from .installation_inspection_form_4945 import (
    INSPECTION_IDS, SURVEY_IDS,
)
from .installation_receipt_crosscheck_4947 import (
    compare_installation_to_receipt,
)


def values():
    return {
        "manager_findings": {
            key: "YES" for key in INSPECTION_IDS
        },
        "receipt_inspection_answers": {
            key: "YES" for key in INSPECTION_IDS
        },
        "receipt_survey_answers": {
            key: None for key in SURVEY_IDS
        },
    }


class InstallationReceiptCrosscheckTests(TestCase):
    def test_all_agreements_without_survey(self):
        result = compare_installation_to_receipt(**values())
        self.assertEqual(result.review_candidate_ids, ())
        self.assertEqual(result.discrepancy_ids, ())
        self.assertEqual(result.survey_answered_count, 0)
        self.assertEqual(
            [row.status for row in result.comparisons],
            ["AGREEMENT_YES"] * 5,
        )
        self.assertFalse(result.receipt_customer_provenance_verified)
        self.assertFalse(result.completion_authorized)

    def test_manager_yes_customer_no_flags_discrepancy(self):
        data = values()
        data["receipt_inspection_answers"]["inspection_4"] = "NO"
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.discrepancy_ids, ("inspection_4",))
        self.assertEqual(result.review_candidate_ids, ("inspection_4",))
        self.assertEqual(result.customer_negative_ids, ("inspection_4",))

    def test_manager_no_customer_yes_flags_discrepancy(self):
        data = values()
        data["manager_findings"]["inspection_2"] = "NO"
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.discrepancy_ids, ("inspection_2",))
        self.assertEqual(result.manager_negative_ids, ("inspection_2",))

    def test_both_no_requires_review(self):
        data = values()
        data["manager_findings"]["inspection_3"] = "NO"
        data["receipt_inspection_answers"]["inspection_3"] = "NO"
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.discrepancy_ids, ())
        self.assertEqual(result.review_candidate_ids, ("inspection_3",))
        self.assertEqual(result.comparisons[2].status, "AGREEMENT_NO")

    def test_missing_customer_answer_not_fabricated(self):
        data = values()
        data["receipt_inspection_answers"]["inspection_1"] = None
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.discrepancy_ids, ())
        self.assertEqual(result.unanswered_customer_ids, ("inspection_1",))
        self.assertEqual(
            result.comparisons[0].status, "CUSTOMER_UNANSWERED"
        )

    def test_missing_manager_answer_requires_review(self):
        data = values()
        data["manager_findings"]["inspection_5"] = None
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.review_candidate_ids, ("inspection_5",))
        self.assertEqual(
            result.comparisons[4].status, "MANAGER_UNANSWERED"
        )

    def test_negative_survey_is_feedback_not_inspection_failure(self):
        data = values()
        data["receipt_survey_answers"]["survey_3"] = "NO"
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.survey_answered_count, 1)
        self.assertEqual(result.review_candidate_ids, ())
        self.assertFalse(result.action_items_persisted)
        self.assertFalse(result.completion_authorized)

    def test_invalid_answer_rejected(self):
        data = values()
        data["receipt_inspection_answers"]["inspection_2"] = "PASS"
        with self.assertRaises(ValidationError):
            compare_installation_to_receipt(**data)

    def test_missing_or_extra_question_rejected(self):
        data = values()
        del data["receipt_inspection_answers"]["inspection_1"]
        with self.assertRaises(ValidationError):
            compare_installation_to_receipt(**data)

        data = values()
        data["receipt_survey_answers"]["survey_4"] = "YES"
        with self.assertRaises(ValidationError):
            compare_installation_to_receipt(**data)

    def test_customer_claim_never_promotes_trust(self):
        data = values()
        data["receipt_survey_answers"]["survey_1"] = "YES"
        result = compare_installation_to_receipt(**data)
        self.assertEqual(result.status, "OFFLINE_COMPARISON_UNVERIFIED")
        self.assertFalse(result.receipt_customer_provenance_verified)
        self.assertFalse(result.installation_signature_verified)
        self.assertFalse(result.action_items_persisted)
        self.assertFalse(result.completion_authorized)
