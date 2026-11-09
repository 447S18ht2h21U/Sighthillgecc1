"""Isolated database authorization and completion denial tests."""
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Project, User
from .project_completion_preflight import (
    assess_project_completion_preflight,
)
from . import test_installation_combined_real_evidence as fixtures


class ProjectCompletionPreflightTests(TestCase):
    def setUp(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.msr = fixture.prepare()
        self.project = fixture.project
        self.actor = User.objects.get(pk=self.msr.created_by_id)

    def assess(self, actor=None):
        return assess_project_completion_preflight(
            actor=self.actor if actor is None else actor,
            project_id=self.project.pk,
        )

    def test_real_project_missing_proof_denied(self):
        with patch(
            "core.project_completion_preflight.authorize"
        ) as authorization:
            result = self.assess()

        authorization.assert_called_once()
        self.assertEqual(
            result.current_approved_msr_id,
            str(self.msr.pk),
        )
        self.assertFalse(result.receipt_email_authenticated)
        self.assertFalse(result.docusign_completion_authenticated)
        self.assertFalse(result.completion_authorized)
        self.assertFalse(result.project_completed)
        self.assertTrue(result.blockers)

    def test_existing_authorization_denial_preserved(self):
        with patch(
            "core.project_completion_preflight.authorize",
            side_effect=PermissionDenied("Denied by existing policy"),
        ):
            with self.assertRaises(PermissionDenied):
                self.assess()

    def test_inactive_actor_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        with patch(
            "core.project_completion_preflight.authorize"
        ) as auth:
            with self.assertRaises(PermissionDenied):
                self.assess()
        auth.assert_not_called()

    def test_missing_approved_msr_denied(self):
        self.project.current_approved = None
        self.project.save(update_fields=["current_approved"])

        with patch("core.project_completion_preflight.authorize"):
            with self.assertRaises(ValidationError):
                self.assess()

    def test_cancelled_project_denied(self):
        self.project.state = "CANCELLED"
        self.project.save(update_fields=["state"])

        with patch("core.project_completion_preflight.authorize"):
            with self.assertRaises(ValidationError):
                self.assess()

    def test_survey_is_optional_and_state_unchanged(self):
        original = self.project.state

        with patch("core.project_completion_preflight.authorize"):
            result = self.assess()

        self.assertFalse(result.satisfaction_survey_required)
        self.project.refresh_from_db()
        self.assertEqual(self.project.state, original)
        self.assertFalse(result.completion_authorized)