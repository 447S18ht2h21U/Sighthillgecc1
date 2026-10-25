"""Regression tests for read-only completion verification eligibility."""

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import release, test_release as release_tests
from .completion_signature_eligibility import require_verification_eligibility


@override_settings(DEBUG=True)
class CompletionSignatureEligibilityTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    authorize_test_customer = release_tests.ReleaseTests.authorize_test_customer
    approval = release_tests.ReleaseTests.approval

    def test_active_comptroller_with_approved_package(self):
        self.setup_release(completion=True)
        self.approval()
        result = require_verification_eligibility(self.comptroller, self.package)
        self.assertEqual(result["release_package_id"], str(self.package.pk))
        self.assertEqual(result["package_digest"], self.package.digest)
        self.assertTrue(result["eligible_for_verification_review"])
        self.assertFalse(result["provider_verified"])

    def test_other_role_and_inactive_comptroller_rejected(self):
        self.setup_release(completion=True)
        self.approval()
        with self.assertRaises(PermissionDenied):
            require_verification_eligibility(self.manager, self.package)
        self.comptroller.is_active = False
        with self.assertRaises(PermissionDenied):
            require_verification_eligibility(self.comptroller, self.package)

    def test_unapproved_or_revoked_package_rejected(self):
        self.setup_release(completion=True)
        with self.assertRaises(ValidationError):
            require_verification_eligibility(self.comptroller, self.package)
        self.approval()
        release.decide(self.comptroller, self.package.id, {"decision": "REVOKED", "note": "Synthetic withdrawal"})
        with self.assertRaises(ValidationError):
            require_verification_eligibility(self.comptroller, self.package)

    def test_missing_or_tampered_package_rejected(self):
        self.setup_release(completion=True)
        self.approval()
        with self.assertRaises(ValidationError):
            require_verification_eligibility(self.comptroller, None)
        self.package.digest = "0" * 64
        with self.assertRaises(ValidationError):
            require_verification_eligibility(self.comptroller, self.package)

    def test_commercial_release_cannot_qualify(self):
        self.setup_release(completion=False)
        self.approval()
        self.assertEqual(release.status(self.package)["status"], "APPROVED")
        self.assertEqual(self.package.plan.group, "COMMERCIAL")
        with self.assertRaises(ValidationError):
            require_verification_eligibility(self.comptroller, self.package)
