"""Completion envelope cancellation transaction tests."""
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied
from . import test_release as release_tests
from .completion_envelope_service import create_attempt
from .completion_envelope_cancellation import cancel_unsent_attempt
from .models import CompletionEnvelopeAttempt

@override_settings(DEBUG=True)
class CompletionEnvelopeCancellationTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    approve = release_tests.ReleaseTests.approve
    authorize_test_customer = release_tests.ReleaseTests.authorize_test_customer
    approval = release_tests.ReleaseTests.approval

    def test_unauthorized_cancellation_rejected(self):
        self.setup_release(completion=True)
        self.approval()
        attempt = create_attempt(self.comptroller, self.package.id, "11111111-1111-4111-8111-111111111111")
        with self.assertRaises(PermissionDenied):
            cancel_unsent_attempt(self.manager, attempt.id)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "AUTH_PENDING")

    def test_comptroller_cancels_unsent_attempt(self):
        from .models import AuditEvent
        self.setup_release(completion=True)
        self.approval()
        attempt = create_attempt(self.comptroller, self.package.id, "11111111-1111-4111-8111-111111111111")
        result = cancel_unsent_attempt(self.comptroller, attempt.id)
        self.assertEqual(result.state, "CANCELLED_UNSENT")
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "CANCELLED_UNSENT")
        self.assertTrue(CompletionEnvelopeAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action="completion_envelope.cancelled_unsent").exists())

    def test_repeated_cancellation_rejected(self):
        from rest_framework.exceptions import ValidationError
        self.setup_release(completion=True)
        self.approval()
        attempt = create_attempt(self.comptroller, self.package.id, "11111111-1111-4111-8111-111111111111")
        cancel_unsent_attempt(self.comptroller, attempt.id)
        with self.assertRaises(ValidationError):
            cancel_unsent_attempt(self.comptroller, attempt.id)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "CANCELLED_UNSENT")

    def test_database_rejects_unauthorized_send_timestamp(self):
        from django.db import DatabaseError, transaction
        from django.utils import timezone

        self.setup_release(completion=True)
        self.approval()
        attempt = create_attempt(
            self.comptroller, self.package.id,
            "11111111-1111-4111-8111-111111111111"
        )

        attempt.first_send_started_at = timezone.now()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                attempt.save(update_fields=["first_send_started_at"])

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "AUTH_PENDING")
        self.assertIsNone(attempt.first_send_started_at)

    def test_historical_send_activity_prevents_cancellation(self):
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.exceptions import ValidationError
        from .models import AuditEvent

        self.setup_release(completion=True)
        self.approval()
        attempt = create_attempt(
            self.comptroller, self.package.id,
            "11111111-1111-4111-8111-111111111111"
        )

        historical_attempt = CompletionEnvelopeAttempt.objects.get(pk=attempt.pk)
        historical_attempt.state = "SEND_UNCERTAIN"
        historical_attempt.first_send_started_at = timezone.now()

        with patch(
            "core.completion_envelope_cancellation.CompletionEnvelopeAttempt.objects.select_for_update"
        ) as select_for_update:
            select_for_update.return_value.select_related.return_value.get.return_value = historical_attempt
            with self.assertRaises(ValidationError):
                cancel_unsent_attempt(self.comptroller, attempt.pk)

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "AUTH_PENDING")
        self.assertIsNone(attempt.first_send_started_at)
        self.assertFalse(
            AuditEvent.objects.filter(
                action="completion_envelope.cancelled_unsent"
            ).exists()
        )

    def test_cancellation_rolls_back_if_audit_fails(self):
        from unittest.mock import patch
        self.setup_release(completion=True)
        self.approval()
        attempt = create_attempt(self.comptroller, self.package.id, "11111111-1111-4111-8111-111111111111")
        with patch("core.completion_envelope_cancellation.audit", side_effect=RuntimeError("Synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                cancel_unsent_attempt(self.comptroller, attempt.id)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "AUTH_PENDING")
