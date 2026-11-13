"""Operational completion-status API acceptance.

Disposable Django database only. Tests do not send envelopes,
authenticate provider signatures, or authorize completion.
"""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from . import test_completion_retention_database_4616 as attempts
from . import test_installation_combined_real_evidence as fixtures
from .models import CompletionEnvelopeAttempt


class RecordedCompletionStatusTests(TestCase):
    setUp = attempts.CompletionRetentionDatabaseTests.setUp

    def url(self):
        return reverse(
            "operational-projects-completion-signature-status",
            kwargs={"pk": str(self.project.pk)},
        )

    def client_as(self, actor):
        client = APIClient()
        if actor is not None:
            client.force_authenticate(user=actor)
        return client

    def verify_untrusted(self, payload):
        self.assertEqual(
            payload["project_id"], str(self.project.pk)
        )
        self.assertIs(payload["read_only"], True)
        self.assertIs(payload["provider_verified"], False)
        self.assertIs(
            payload["installation_complete_qualified"], False
        )
        self.assertIs(payload["completion_authorized"], False)
        self.assertIs(payload["retry_authorized"], False)
        self.assertIsInstance(payload["attempt_count"], int)
        self.assertGreaterEqual(payload["attempt_count"], 0)
        self.assertEqual(
            sum(item["count"] for item in payload["attempt_states"]),
            payload["attempt_count"],
        )

    def test_authorized_reviewer_sees_pending_attempt_not_signature(self):
        initial_state = self.project.state

        response = self.client_as(self.comptroller).get(self.url())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.verify_untrusted(payload)

        self.assertEqual(payload["status"], "ATTEMPTS_UNVERIFIED")
        self.assertEqual(payload["attempt_count"], 1)
        self.assertEqual(
            payload["attempt_states"],
            [{"state": "AUTH_PENDING", "count": 1}],
        )

        self.project.refresh_from_db()
        self.attempt.refresh_from_db()

        self.assertEqual(self.project.state, initial_state)
        self.assertEqual(self.attempt.state, "AUTH_PENDING")
        self.assertEqual(self.attempt.provider_envelope_id, "")

    def test_missing_attempt_table_fails_closed(self):
        with patch.object(
            connection.introspection,
            "table_names",
            return_value=[],
        ):
            response = self.client_as(
                self.comptroller
            ).get(self.url())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.verify_untrusted(payload)

        self.assertEqual(payload["status"], "SCHEMA_UNAVAILABLE")
        self.assertEqual(payload["attempt_count"], 0)
        self.assertEqual(payload["attempt_states"], [])

    def test_unauthenticated_user_cannot_read_attempt_status(self):
        response = self.client_as(None).get(self.url())
        self.assertIn(response.status_code, (401, 403))

    def test_cancelled_project_returns_no_attempt_details(self):
        type(self.project).objects.filter(
            pk=self.project.pk
        ).update(state="CANCELLED")

        response = self.client_as(self.comptroller).get(self.url())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.verify_untrusted(payload)
        self.assertEqual(payload["status"], "PREREQUISITES_MISSING")
        self.assertEqual(payload["attempt_count"], 0)
        self.assertEqual(payload["attempt_states"], [])


class ProjectVisibilityStatusTests(TestCase):
    def setUp(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        fixture.prepare()

        self.project = fixture.project
        self.comptroller = fixture.comptroller
        self.other = fixture.other

        self.url = reverse(
            "operational-projects-completion-signature-status",
            kwargs={"pk": str(self.project.pk)},
        )

    def test_sales_associate_cannot_access_completion_status(self):
        client = APIClient()
        client.force_authenticate(user=self.other)

        response = client.get(self.url)
        self.assertIn(response.status_code, (403, 404))

    def test_no_attempts_are_not_treated_as_verified(self):
        self.assertFalse(
            CompletionEnvelopeAttempt.objects.filter(
                release_package__plan__msr_id=
                    self.project.current_approved_id
            ).exists()
        )

        client = APIClient()
        client.force_authenticate(user=self.comptroller)

        response = client.get(self.url)

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], "NO_ATTEMPTS")
        self.assertEqual(payload["attempt_count"], 0)
        self.assertEqual(payload["attempt_states"], [])
        self.assertIs(payload["provider_verified"], False)
        self.assertIs(payload["completion_authorized"], False)
        self.assertIs(payload["retry_authorized"], False)
