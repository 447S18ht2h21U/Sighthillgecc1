from hashlib import sha256
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_inspection_form_4945 import (
    INSPECTION_IDS, SURVEY_IDS,
    INSPECTION_ITEMS, SURVEY_ITEMS,
    assess_inspection_answers, render_unsigned_inspection_form,
)
from .test_installation_attestation_pdf_4942 import manifest

MODULE = "core.installation_inspection_form_4945"


def answers():
    return (
        {key: "YES" for key in INSPECTION_IDS},
        {key: None for key in SURVEY_IDS},
    )


class ApprovedInspectionFormTests(TestCase):
    def test_approved_question_counts(self):
        self.assertEqual(len(INSPECTION_ITEMS), 5)
        self.assertEqual(len(SURVEY_ITEMS), 3)

    def test_yes_inspection_without_survey_is_review_ready(self):
        inspection, survey = answers()
        result = assess_inspection_answers(
            inspection=inspection, survey=survey
        )
        self.assertTrue(result.inspection_review_ready)
        self.assertEqual(result.survey_answered_count, 0)
        self.assertFalse(result.project_completion_authorized)

    def test_no_inspection_creates_corrective_action(self):
        inspection, survey = answers()
        inspection["inspection_3"] = "NO"
        result = assess_inspection_answers(
            inspection=inspection, survey=survey
        )
        self.assertEqual(
            result.corrective_action_items, ("inspection_3",)
        )
        self.assertFalse(result.inspection_review_ready)

    def test_multiple_failures_retained(self):
        inspection, survey = answers()
        inspection["inspection_2"] = "NO"
        inspection["inspection_4"] = "NO"
        result = assess_inspection_answers(
            inspection=inspection, survey=survey
        )
        self.assertEqual(
            result.corrective_action_items,
            ("inspection_2", "inspection_4")
        )

    def test_unanswered_inspection_not_ready(self):
        inspection, survey = answers()
        inspection["inspection_1"] = None
        result = assess_inspection_answers(
            inspection=inspection, survey=survey
        )
        self.assertFalse(result.inspection_review_ready)
        self.assertEqual(
            result.unanswered_inspection_items, ("inspection_1",)
        )

    def test_survey_is_optional(self):
        inspection, survey = answers()
        survey["survey_1"] = "NO"
        survey["survey_2"] = "YES"
        result = assess_inspection_answers(
            inspection=inspection, survey=survey
        )
        self.assertTrue(result.inspection_review_ready)
        self.assertEqual(result.survey_answered_count, 2)
        self.assertFalse(
            result.customer_satisfaction_required_for_completion
        )

    def test_invalid_answers_rejected(self):
        inspection, survey = answers()
        inspection["inspection_2"] = "PASS"
        with self.assertRaises(ValidationError):
            assess_inspection_answers(
                inspection=inspection, survey=survey
            )

    def test_extra_questions_rejected(self):
        inspection, survey = answers()
        survey["survey_4"] = "YES"
        with self.assertRaises(ValidationError):
            assess_inspection_answers(
                inspection=inspection, survey=survey
            )

    @patch(MODULE + ".settings")
    @patch(MODULE + ".build_installation_signing_manifest")
    def test_pdf_has_blank_fields_and_no_trust(self, builder, settings):
        settings.ENVIRONMENT = "development"
        settings.DEBUG = True
        builder.return_value = manifest()
        result = render_unsigned_inspection_form(
            actor=SimpleNamespace(pk="synthetic-ceo-4945"),
            project_id="synthetic-project-4945",
        )
        self.assertTrue(result.pdf.startswith(b"%PDF-"))
        self.assertEqual(
            sha256(result.pdf).hexdigest(), result.pdf_sha256
        )
        self.assertFalse(result.inspection_responses_captured)
        self.assertFalse(result.customer_feedback_verified)
        self.assertFalse(result.docusign_tabs_configured)
        self.assertFalse(result.provider_authenticated)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.completion_authorized)

    @patch(MODULE + ".settings")
    def test_production_pdf_generation_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            render_unsigned_inspection_form(
                actor=None, project_id="synthetic-project-4945"
            )
