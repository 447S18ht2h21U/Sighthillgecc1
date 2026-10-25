"""Database safeguards for completion envelope attempts."""

from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import CompletionEnvelopeAttempt
from . import test_release as release_tests


@override_settings(DEBUG=True)
class CompletionEnvelopeAttemptTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    authorize_test_customer = release_tests.ReleaseTests.authorize_test_customer

    def make_attempt(self):
        self.setup_release(completion=True)
        return CompletionEnvelopeAttempt.objects.create(
            release_package=self.package, initiated_by=self.comptroller,
            provider_account_id="11111111-1111-4111-8111-111111111111")

    def test_database_rejects_deletion(self):
        attempt = self.make_attempt()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(pk=attempt.pk).delete()
        self.assertTrue(CompletionEnvelopeAttempt.objects.filter(pk=attempt.pk).exists())

    def test_release_package_allows_only_one_attempt(self):
        attempt = self.make_attempt()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.create(
                    release_package=self.package, initiated_by=self.comptroller,
                    provider_account_id=attempt.provider_account_id)
        self.assertEqual(CompletionEnvelopeAttempt.objects.filter(release_package=self.package).count(), 1)

    def test_database_rejects_unauthorized_sending_transition(self):
        attempt = self.make_attempt()
        attempt.state = "NETWORK_STARTED"
        attempt.first_send_started_at = timezone.now()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                attempt.save(update_fields=["state", "first_send_started_at"])

        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "AUTH_PENDING")
        self.assertIsNone(attempt.first_send_started_at)
