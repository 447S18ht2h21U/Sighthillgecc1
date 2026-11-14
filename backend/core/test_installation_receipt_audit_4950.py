from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from .installation_inspection_form_4945 import (
    INSPECTION_IDS, SURVEY_IDS,
)
from .installation_receipt_audit_4950 import (
    compare_receipt_survey_to_inspection,
    DIRECT_MAPPING, CONTEXT_MAPPING,
)


MODULE = "core.installation_receipt_audit_4950"


def inputs():
    return {
        "manager_findings": {
            key: "YES" for key in INSPECTION_IDS
        },
        "customer_survey_candidates": {
            key: None for key in SURVEY_IDS
        },
    }


@patch(MODULE + ".verify_approved_final_receipt")
class ReceiptAuditTests(TestCase):
    def test_mapping_contains_one_direct_comparison(self, reference):
        reference.return_value.sha256 = "a" * 64
        self.assertEqual(DIRECT_MAPPING, {"survey_1": "inspection_4"})
        self.assertEqual(
            CONTEXT_MAPPING["survey_2"],
            ("inspection_2", "inspection_3"),
        )

    def test_optional_unanswered_survey(self, reference):
        reference.return_value.sha256 = "a" * 64
        result = compare_receipt_survey_to_inspection(**inputs())
        self.assertEqual(result.customer_survey_answered_count, 0)
        self.assertEqual(result.review_candidate_ids, ())
        self.assertFalse(result.customer_survey_required_for_completion)
        self.assertFalse(result.completion_authorized)

    def test_cleanup_agreement(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["customer_survey_candidates"]["survey_1"] = "YES"
        result = compare_receipt_survey_to_inspection(**data)
        self.assertEqual(result.findings[0].assessment, "AGREEMENT")
        self.assertEqual(result.direct_discrepancy_ids, ())

    def test_cleanup_disagreement(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["customer_survey_candidates"]["survey_1"] = "NO"
        result = compare_receipt_survey_to_inspection(**data)
        self.assertEqual(
            result.direct_discrepancy_ids, ("survey_1",)
        )
        self.assertEqual(result.review_candidate_ids, ("inspection_4",))

    def test_professionalism_is_context_not_exact_match(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["customer_survey_candidates"]["survey_2"] = "NO"
        result = compare_receipt_survey_to_inspection(**data)
        self.assertEqual(
            result.findings[1].assessment,
            "RELATED_FEEDBACK_NO_DIRECT_COMPARISON",
        )
        self.assertEqual(result.direct_discrepancy_ids, ())
        self.assertEqual(
            result.review_candidate_ids,
            ("inspection_2", "inspection_3"),
        )

    def test_referral_is_context_not_physical_proof(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["customer_survey_candidates"]["survey_3"] = "NO"
        result = compare_receipt_survey_to_inspection(**data)
        self.assertEqual(result.direct_discrepancy_ids, ())
        self.assertEqual(result.review_candidate_ids, ("inspection_5",))

    def test_manager_negative_still_creates_review(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["manager_findings"]["inspection_3"] = "NO"
        result = compare_receipt_survey_to_inspection(**data)
        self.assertEqual(result.manager_negative_ids, ("inspection_3",))
        self.assertEqual(result.review_candidate_ids, ("inspection_3",))

    def test_missing_manager_finding_needs_review(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["manager_findings"]["inspection_1"] = None
        result = compare_receipt_survey_to_inspection(**data)
        self.assertEqual(
            result.manager_unanswered_ids, ("inspection_1",)
        )
        self.assertEqual(result.review_candidate_ids, ("inspection_1",))

    def test_fabricated_five_customer_fields_rejected(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["customer_survey_candidates"]["inspection_1"] = "YES"
        with self.assertRaises(ValidationError):
            compare_receipt_survey_to_inspection(**data)

    def test_no_false_customer_authentication(self, reference):
        reference.return_value.sha256 = "a" * 64
        data = inputs()
        data["customer_survey_candidates"]["survey_1"] = "YES"
        result = compare_receipt_survey_to_inspection(**data)
        self.assertFalse(result.customer_provenance_verified)
        self.assertFalse(result.manager_signature_verified)
        self.assertFalse(result.corrective_actions_persisted)
        self.assertFalse(result.completion_authorized)
