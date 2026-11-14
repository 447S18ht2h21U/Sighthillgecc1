from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .test_installation_docusign_placement_4960 import (
    actual_form_and_contract,
)
from .installation_docusign_placement_4960 import (
    build_offline_inspection_tab_plan,
)
from .installation_docusign_envelope_4962 import (
    build_offline_installation_envelope,
)
from .installation_signing_findings_4963 import (
    evaluate_inspection_response_candidate,
)

M = "core.installation_signing_findings_4963"


def setup():
    form, contract = actual_form_and_contract()
    plan = build_offline_inspection_tab_plan(
        contract=contract, pdf_bytes=form.pdf
    )
    return build_offline_installation_envelope(
        contract=contract, plan=plan, unsigned_pdf=form.pdf
    )


def answers():
    return {
        f"inspection_{i}": ["YES"] for i in range(1, 6)
    }


class InspectionSigningFindings4963Tests(TestCase):
    def test_five_positive_answers_only_candidate(self):
        result = evaluate_inspection_response_candidate(
            envelope=setup(), selections=answers()
        )
        self.assertTrue(result.response_set_complete)
        self.assertEqual(result.review_candidates, ())
        self.assertFalse(result.provider_response_authenticated)
        self.assertFalse(result.signature_verified)
        self.assertFalse(result.signed_date_verified)
        self.assertFalse(result.completion_authorized)

    def test_negative_creates_corrective_action_candidate(self):
        values = answers()
        values["inspection_4"] = ["NO"]
        result = evaluate_inspection_response_candidate(
            envelope=setup(), selections=values
        )
        self.assertEqual(len(result.review_candidates), 1)
        self.assertEqual(
            result.review_candidates[0].reason,
            "MANAGER_NEGATIVE_CANDIDATE",
        )
        self.assertFalse(result.work_orders_created)

    def test_multiple_negative_findings(self):
        values = answers()
        values["inspection_2"] = ["NO"]
        values["inspection_5"] = ["NO"]
        result = evaluate_inspection_response_candidate(
            envelope=setup(), selections=values
        )
        self.assertEqual(
            [item.inspection_id for item in result.review_candidates],
            ["inspection_2", "inspection_5"],
        )

    def test_unanswered_required_question(self):
        values = answers()
        values["inspection_3"] = []
        result = evaluate_inspection_response_candidate(
            envelope=setup(), selections=values
        )
        self.assertFalse(result.response_set_complete)
        self.assertEqual(
            result.review_candidates[0].reason,
            "REQUIRED_RESPONSE_MISSING",
        )

    def test_double_selection_denied(self):
        values = answers()
        values["inspection_1"] = ["YES", "NO"]
        with self.assertRaises(ValidationError):
            evaluate_inspection_response_candidate(
                envelope=setup(), selections=values
            )

    def test_customer_survey_answer_denied(self):
        values = answers()
        values["survey_1"] = ["YES"]
        with self.assertRaises(ValidationError):
            evaluate_inspection_response_candidate(
                envelope=setup(), selections=values
            )

    def test_modified_envelope_authority_denied(self):
        with self.assertRaises(ValidationError):
            evaluate_inspection_response_candidate(
                envelope=replace(setup(), provider_signed=True),
                selections=answers(),
            )

    def test_deterministic_snapshot_ignores_mutation(self):
        values = answers()
        envelope = setup()
        first = evaluate_inspection_response_candidate(
            envelope=envelope, selections=values
        )
        second = evaluate_inspection_response_candidate(
            envelope=envelope, selections=values
        )
        values["inspection_1"][0] = "NO"
        self.assertEqual(first.response_sha256, second.response_sha256)
        self.assertEqual(dict(first.selections)["inspection_1"], "YES")

    @patch(M + ".settings")
    def test_production_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            evaluate_inspection_response_candidate(
                envelope=None, selections=None
            )
