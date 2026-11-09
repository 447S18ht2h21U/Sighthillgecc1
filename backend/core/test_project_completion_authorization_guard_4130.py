"""Nine fail-closed security tests."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .project_completion_authorization_guard import (
    require_verified_project_completion,
)
from .project_completion_preflight import ProjectCompletionPreflight


class CompletionGuardTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=uuid4())
        self.project = str(uuid4())
        self.report = ProjectCompletionPreflight(
            project_id=self.project,
            current_approved_msr_id=str(uuid4()),
            receipt_candidates=0,
            unverified_email_observations=0,
            certificate_candidates=0,
            receipt_email_authenticated=False,
            docusign_completion_authenticated=False,
            satisfaction_survey_required=False,
            blockers=("Missing trusted evidence.",),
        )

    def check(self, report):
        with patch(
            "core.project_completion_authorization_guard."
            "assess_project_completion_preflight",
            return_value=report,
        ) as inspected:
            try:
                return require_verified_project_completion(
                    actor=self.actor, project_id=self.project
                )
            finally:
                inspected.assert_called_once()

    def test_missing_evidence_denied(self):
        with self.assertRaises(PermissionDenied):
            self.check(self.report)

    def test_local_pdfs_cannot_authorize(self):
        with self.assertRaises(PermissionDenied):
            self.check(replace(
                self.report, receipt_candidates=8, certificate_candidates=8
            ))

    def test_synthetic_email_cannot_authorize(self):
        with self.assertRaises(PermissionDenied):
            self.check(replace(
                self.report, unverified_email_observations=500
            ))

    def test_forged_receipt_trust_denied(self):
        with self.assertRaises(ValidationError):
            self.check(replace(
                self.report, receipt_email_authenticated=True
            ))

    def test_forged_docusign_trust_denied(self):
        with self.assertRaises(ValidationError):
            self.check(replace(
                self.report, docusign_completion_authenticated=True
            ))

    def test_forged_authorization_denied(self):
        with self.assertRaises(ValidationError):
            self.check(replace(
                self.report, completion_authorized=True
            ))

    def test_forged_completed_state_denied(self):
        with self.assertRaises(ValidationError):
            self.check(replace(
                self.report, project_completed=True
            ))

    def test_survey_optional(self):
        self.assertFalse(self.report.satisfaction_survey_required)
        with self.assertRaises(PermissionDenied) as caught:
            self.check(self.report)
        self.assertIn("optional", str(caught.exception).lower())

    def test_authorization_failure_propagates(self):
        with patch(
            "core.project_completion_authorization_guard."
            "assess_project_completion_preflight",
            side_effect=PermissionDenied("Original access policy denied."),
        ):
            with self.assertRaises(PermissionDenied):
                require_verified_project_completion(
                    actor=self.actor, project_id=self.project
                )