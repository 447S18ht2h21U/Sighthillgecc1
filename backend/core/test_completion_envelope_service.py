"""Completion-envelope attempt eligibility regression tests."""

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import CompletionEnvelopeAttempt
from .completion_envelope_service import require_attempt_eligibility
from . import test_release as release_tests


@override_settings(DEBUG=True)
class CompletionEnvelopeServiceTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    authorize_test_customer = release_tests.ReleaseTests.authorize_test_customer
    approval = release_tests.ReleaseTests.approval

    def test_approved_completion_release_is_eligible(self):
        self.setup_release(completion=True)
        self.approval()
        result = require_attempt_eligibility(self.comptroller, self.package)
        self.assertTrue(result["attempt_creation_eligible"])
        self.assertFalse(result["send_available"])
        self.assertFalse(result["provider_authenticated"])

    def test_existing_attempt_blocks_new_attempt(self):
        self.setup_release(completion=True)
        self.approval()
        CompletionEnvelopeAttempt.objects.create(
            release_package=self.package, initiated_by=self.comptroller,
            provider_account_id="11111111-1111-4111-8111-111111111111")
        with self.assertRaises(ValidationError):
            require_attempt_eligibility(self.comptroller, self.package)

    def test_unauthorized_user_is_rejected(self):
        self.setup_release(completion=True)
        self.approval()
        with self.assertRaises(PermissionDenied):
            require_attempt_eligibility(self.manager, self.package)

    def test_existing_attempt_blocks_new_release_package(self):
        from . import release
        self.setup_release(completion=True)
        original = self.package
        self.approval()
        CompletionEnvelopeAttempt.objects.create(
            release_package=original, initiated_by=self.comptroller,
            provider_account_id="11111111-1111-4111-8111-111111111111")
        updated = {**self.evidence_data, "verification_note": "Updated synthetic completion evidence"}
        release.record_evidence(self.comptroller, self.approved.id, updated)
        newer, created = release.prepare_package(self.comptroller, self.plan.id)
        self.assertTrue(created)
        self.assertNotEqual(original.pk, newer.pk)
        self.package = newer
        self.approval()
        with self.assertRaises(ValidationError):
            require_attempt_eligibility(self.comptroller, newer)

    def test_attempt_creation_and_audit(self):
        from .models import AuditEvent
        from .completion_envelope_service import create_attempt
        self.setup_release(completion=True)
        self.approval()
        account = "11111111-1111-4111-8111-111111111111"
        attempt = create_attempt(self.comptroller, self.package.id, account)
        self.assertEqual(attempt.initiated_by_id, self.comptroller.id)
        self.assertEqual(attempt.release_package_id, self.package.id)
        self.assertEqual(attempt.state, "AUTH_PENDING")
        self.assertEqual(attempt.provider_account_id, account)
        self.assertTrue(AuditEvent.objects.filter(action="completion_envelope.attempt_created").exists())
        with self.assertRaises(ValidationError):
            create_attempt(self.comptroller, self.package.id, account)

    def test_attempt_creation_rejects_unauthorized_user(self):
        from .completion_envelope_service import create_attempt
        self.setup_release(completion=True)
        self.approval()
        with self.assertRaises(PermissionDenied):
            create_attempt(self.manager, self.package.id, "11111111-1111-4111-8111-111111111111")
        self.assertFalse(CompletionEnvelopeAttempt.objects.exists())

    def test_attempt_creation_rolls_back_if_audit_fails(self):
        from unittest.mock import patch
        from .completion_envelope_service import create_attempt
        self.setup_release(completion=True)
        self.approval()
        with patch("core.completion_envelope_service.audit", side_effect=RuntimeError("Synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                create_attempt(self.comptroller, self.package.id, "11111111-1111-4111-8111-111111111111")
        self.assertFalse(CompletionEnvelopeAttempt.objects.exists())
