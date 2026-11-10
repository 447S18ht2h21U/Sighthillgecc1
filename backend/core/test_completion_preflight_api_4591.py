"""Security regression for read-only completion preflight API.

Uses disposable Django test records. No operational state transitions.
"""
from dataclasses import replace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from . import test_installation_combined_real_evidence as fixtures
from .project_completion_preflight import ProjectCompletionPreflight


class CompletionPreflightAPISecurityTests(TestCase):
    def setUp(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        fixture.prepare()

        self.project = fixture.project
        self.manager = fixture.manager
        self.comptroller = fixture.comptroller
        self.other = fixture.other
        self.client = APIClient()
        self.url = reverse(
            "operational-projects-completion-preflight",
            kwargs={"pk": str(self.project.pk)},
        )

    def authenticate(self, actor):
        self.client.force_authenticate(user=actor)

    def test_authenticated_comptroller_receives_denied_preflight(self):
        self.authenticate(self.comptroller)
        initial_state = self.project.state

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()

        self.assertEqual(data["project_id"], str(self.project.pk))
        self.assertEqual(
            data["status"], "COMPLETION_EVIDENCE_UNVERIFIED"
        )
        self.assertIs(data["read_only"], True)
        self.assertIs(data["completion_authorized"], False)
        self.assertIs(data["project_completed"], False)
        self.assertIs(data["receipt_email_authenticated"], False)
        self.assertIs(data["docusign_completion_authenticated"], False)
        self.assertIs(data["satisfaction_survey_required"], False)
        self.assertTrue(data["blockers"])

        self.project.refresh_from_db()
        self.assertEqual(self.project.state, initial_state)

    def test_unrelated_sales_associate_cannot_inspect_evidence(self):
        self.authenticate(self.other)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (403, 404))

    def test_unauthenticated_request_is_denied(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_missing_evidence_storage_fails_closed(self):
        self.authenticate(self.comptroller)

        with patch.object(
            connection.introspection,
            "table_names",
            return_value=[],
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(
            data["status"], "EVIDENCE_STORAGE_UNAVAILABLE"
        )
        self.assertIs(data["read_only"], True)
        self.assertIs(data["completion_authorized"], False)
        self.assertIs(data["project_completed"], False)
        self.assertIs(data["receipt_email_authenticated"], False)
        self.assertIs(data["docusign_completion_authenticated"], False)
        self.assertIs(data["satisfaction_survey_required"], False)
        self.assertTrue(data["blockers"])

    def test_draft_project_returns_blocked_assessment(self):
        self.authenticate(self.comptroller)
        type(self.project).objects.filter(
            pk=self.project.pk
        ).update(current_approved=None, state="DRAFT")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(
            data["status"], "COMPLETION_PREREQUISITES_MISSING"
        )
        self.assertIs(data["read_only"], True)
        self.assertIs(data["completion_authorized"], False)
        self.assertIs(data["project_completed"], False)
        self.assertIs(data["receipt_email_authenticated"], False)
        self.assertIs(data["docusign_completion_authenticated"], False)
        self.assertIs(data["satisfaction_survey_required"], False)
        self.assertTrue(
            any("approved Master Sales Record" in reason
                for reason in data["blockers"])
        )

    def test_cancelled_project_returns_blocked_assessment(self):
        self.authenticate(self.comptroller)
        type(self.project).objects.filter(
            pk=self.project.pk
        ).update(state="CANCELLED")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(
            data["status"], "COMPLETION_PREREQUISITES_MISSING"
        )
        self.assertIs(data["completion_authorized"], False)
        self.assertIs(data["project_completed"], False)
        self.assertTrue(
            any("Cancelled" in reason
                for reason in data["blockers"])
        )

    def test_forged_completion_authority_is_rejected(self):
        self.authenticate(self.comptroller)

        baseline = ProjectCompletionPreflight(
            project_id=str(self.project.pk),
            current_approved_msr_id=str(
                self.project.current_approved_id
            ),
            receipt_candidates=0,
            unverified_email_observations=0,
            certificate_candidates=0,
            receipt_email_authenticated=False,
            docusign_completion_authenticated=False,
            satisfaction_survey_required=False,
            blockers=("Authenticated evidence missing.",),
        )
        forged = replace(baseline, completion_authorized=True)

        with patch(
            "core.project_completion_preflight."
            "assess_project_completion_preflight",
            return_value=forged,
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.state, "COMPLETED")
