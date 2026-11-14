"""Focused integration tests for post-installation acceptance verification."""
from django.test import TestCase, override_settings

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .post_installation_acceptance_verifier_4820 import (
    verify_post_installation_acceptance,
)
from .installation_completion_evidence_4815 import (
    assess_installation_completion_evidence,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)
from .models import AuditEvent, ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class AcceptanceVerification4820(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def test_accepted_candidate_is_verified_but_release_blocked(self):
        inspection = self.capture()
        self.review(inspection)

        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )

        verified = verify_post_installation_acceptance(self.project)
        installation = assess_installation_completion_evidence(self.project)
        receipt = assess_final_receipt_release_preflight(self.project)

        self.assertTrue(verified.acceptance_candidate_verified)
        self.assertTrue(installation.acceptance_candidate_verified)
        self.assertTrue(receipt.acceptance_candidate_verified)

        for result in (verified, installation, receipt):
            self.assertFalse(result.trusted_installation_evidence)
            self.assertFalse(result.final_receipt_issuance_authorized)
            self.assertFalse(result.completion_authorized)

        self.assertFalse(receipt.customer_delivery_verified)
        self.assertFalse(receipt.post_installation_acceptance_verified)
        self.assertEqual(before, (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        ))

    def test_missing_independent_review_fails_closed(self):
        self.capture()
        result = verify_post_installation_acceptance(self.project)
        self.assertFalse(result.acceptance_candidate_verified)
        self.assertEqual(result.review_count, 0)
        self.assertFalse(result.final_receipt_issuance_authorized)

    def test_rejected_review_fails_closed(self):
        inspection = self.capture()
        self.review(
            inspection, accept=False, independently_examined=False
        )
        result = verify_post_installation_acceptance(self.project)
        self.assertFalse(result.acceptance_candidate_verified)
        self.assertFalse(result.trusted_installation_evidence)

    def test_failed_inspection_and_rejection_fail_closed(self):
        inspection = self.capture(inspection_passed=False)
        self.review(
            inspection, accept=False, independently_examined=False
        )
        result = verify_post_installation_acceptance(self.project)
        self.assertFalse(result.acceptance_candidate_verified)
        self.assertFalse(result.final_receipt_issuance_authorized)
