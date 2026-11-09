"""Focused regressions for Receipt and completion policy."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .installation_eligibility import ensure_installation_eligible
from .installation_readiness import installation_readiness
from .completion_evidence_policy_preview import (
    preview_project_completion_evidence,
)

NOW = datetime(2026, 11, 2, 17, tzinfo=timezone.utc)


class ReceiptCompletionPolicyTests(SimpleTestCase):
    def check_installation(self, days_ago, payment=True):
        with patch(
            "core.installation_eligibility.require_current_approved_msr",
            return_value=SimpleNamespace(),
        ), patch(
            "core.installation_eligibility.verified_signature_time",
            return_value=NOW - timedelta(days=days_ago),
        ) as signature, patch(
            "core.installation_eligibility.cancellation_deadline",
            return_value=NOW - timedelta(days=1),
        ), patch(
            "core.installation_payment_readiness.installation_payment_readiness",
            return_value={
                "payment_ready": payment,
                "explanation": "Required payment missing.",
            },
        ), patch(
            "core.installation_eligibility.timezone.now",
            return_value=NOW,
        ):
            try:
                result = ensure_installation_eligible(SimpleNamespace())
                return result, signature.call_args_list
            except ValidationError:
                return False, signature.call_args_list

    def test_contract_signature_only(self):
        valid, calls = self.check_installation(7)
        self.assertTrue(valid)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1], "CONTRACT")

    def test_waiting_period_still_blocks(self):
        valid, _ = self.check_installation(2)
        self.assertFalse(valid)

    def test_missing_payment_still_blocks(self):
        valid, _ = self.check_installation(7, False)
        self.assertFalse(valid)

    def test_readiness_has_no_invoice_signature_gate(self):
        result = installation_readiness(SimpleNamespace(current_approved=None))
        self.assertFalse(result["eligible"])
        self.assertNotIn("invoice_signed", result["requirements"])

    def test_retained_receipt_without_email_fails(self):
        result = preview_project_completion_evidence(
            physical_work_verified=True,
            required_inspections_verified=True,
            receipt_pdf_retained=True,
            completed_docusign_certificate_received=True,
            completed_docusign_certificate_retained=True,
        )
        self.assertFalse(result.candidate_requirements_satisfied)
        self.assertTrue(any("email" in item.lower() for item in result.blockers))
        self.assertFalse(result.project_completion_authorized)

    def test_missing_completed_docusign_certificate_fails(self):
        result = preview_project_completion_evidence(
            physical_work_verified=True,
            required_inspections_verified=True,
            receipt_pdf_retained=True,
            receipt_email_delivery_verified=True,
            completed_docusign_certificate_retained=True,
        )
        self.assertFalse(result.candidate_requirements_satisfied)
        self.assertTrue(any("DocuSign" in item for item in result.blockers))

    def test_survey_is_optional_and_authorization_denied(self):
        required = dict(
            physical_work_verified=True,
            required_inspections_verified=True,
            receipt_pdf_retained=True,
            receipt_email_delivery_verified=True,
            completed_docusign_certificate_received=True,
            completed_docusign_certificate_retained=True,
        )
        for survey in (False, True):
            result = preview_project_completion_evidence(
                **required, customer_satisfaction_survey_received=survey
            )
            self.assertTrue(result.candidate_requirements_satisfied)
            self.assertFalse(result.evidence_trusted)
            self.assertFalse(result.project_completion_authorized)
            self.assertFalse(result.project_completed)

    def test_non_boolean_evidence_rejected(self):
        with self.assertRaises(ValueError):
            preview_project_completion_evidence(receipt_pdf_retained="yes")
