"""Regression tests for read-only completion-envelope inspection."""

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .models import CompletionEnvelopeAttempt
from .completion_envelope_inspection import inspect_attempt
from . import test_release as release_tests


@override_settings(DEBUG=True)
class CompletionEnvelopeInspectionTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    authorize_test_customer = release_tests.ReleaseTests.authorize_test_customer
    approval = release_tests.ReleaseTests.approval

    def create_fixture_attempt(self):
        self.setup_release(completion=True)
        self.approval()
        return CompletionEnvelopeAttempt.objects.create(
            release_package=self.package,
            initiated_by=self.comptroller,
            provider_account_id="11111111-1111-4111-8111-111111111111",
        )

    def test_comptroller_can_inspect_existing_attempt(self):
        attempt = self.create_fixture_attempt()
        result = inspect_attempt(self.comptroller, attempt.pk)
        self.assertEqual(result["attempt_id"], str(attempt.pk))
        self.assertEqual(result["release_package_id"], str(self.package.pk))
        self.assertEqual(result["provider_account_id"], attempt.provider_account_id)
        self.assertEqual(result["state"], "AUTH_PENDING")
        self.assertIsNone(result["provider_envelope_id"])

    def test_unauthorized_manager_cannot_inspect(self):
        attempt = self.create_fixture_attempt()
        with self.assertRaises(PermissionDenied):
            inspect_attempt(self.manager, attempt.pk)

    def test_inspection_never_claims_provider_verification(self):
        attempt = self.create_fixture_attempt()
        result = inspect_attempt(self.comptroller, attempt.pk)
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["signature_completion_verified"])
        self.assertFalse(result["send_available"])

    def test_inactive_comptroller_cannot_inspect(self):
        attempt = self.create_fixture_attempt()
        self.comptroller.is_active = False
        with self.assertRaises(PermissionDenied):
            inspect_attempt(self.comptroller, attempt.pk)

    def test_unknown_attempt_is_not_reported_as_verified(self):
        from uuid import uuid4
        from .models import CompletionEnvelopeAttempt
        attempt = self.create_fixture_attempt()
        with self.assertRaises(CompletionEnvelopeAttempt.DoesNotExist):
            inspect_attempt(self.comptroller, uuid4())

    def test_recorded_send_activity_does_not_imply_verification(self):
        from unittest.mock import patch
        from django.utils import timezone

        attempt = self.create_fixture_attempt()
        historical_attempt = CompletionEnvelopeAttempt.objects.get(pk=attempt.pk)
        historical_attempt.state = "SEND_UNCERTAIN"
        historical_attempt.first_send_started_at = timezone.now()

        with patch(
            "core.completion_envelope_inspection.CompletionEnvelopeAttempt.objects.select_related"
        ) as select_related:
            select_related.return_value.get.return_value = historical_attempt
            result = inspect_attempt(self.comptroller, attempt.pk)

        self.assertEqual(result["state"], "SEND_UNCERTAIN")
        self.assertIsNotNone(result["first_send_started_at"])
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["signature_completion_verified"])
        self.assertFalse(result["send_available"])

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "AUTH_PENDING")
        self.assertIsNone(attempt.first_send_started_at)

    def test_inspection_does_not_modify_attempt(self):
        attempt = self.create_fixture_attempt()
        original_state = attempt.state
        inspect_attempt(self.comptroller, attempt.pk)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, original_state)
        self.assertIsNone(attempt.first_send_started_at)
