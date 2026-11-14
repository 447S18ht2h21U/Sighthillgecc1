"""Adversarial tests for persisted acceptance evidence chronology."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .models import ProjectEvidence, User
from .post_installation_acceptance_4819 import (
    INSPECTION_KIND, REVIEW_KIND,
)
from .post_installation_acceptance_verifier_4820 import (
    verify_post_installation_acceptance,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class AcceptanceProvenance4821(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def prepare(self):
        inspection = self.capture()
        review = self.review(inspection)
        return inspection, review

    def verify_with_records(self, inspection, review):
        # Alter only objects in memory, never immutable database records.
        original_filter = ProjectEvidence.objects.filter

        def records(*args, **kwargs):
            kind = kwargs.get("kind")
            if kind == INSPECTION_KIND:
                return [inspection]
            if kind == REVIEW_KIND:
                return [review]
            return original_filter(*args, **kwargs)

        with patch(
            "core.post_installation_acceptance_verifier_4820."
            "ProjectEvidence.objects.filter",
            side_effect=records,
        ):
            return verify_post_installation_acceptance(self.project)

    def assert_blocked(self, result):
        self.assertFalse(result.acceptance_candidate_verified)
        self.assertFalse(result.post_installation_acceptance_verified)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

    def test_persisted_chronology_is_consistent(self):
        self.prepare()
        result = verify_post_installation_acceptance(self.project)
        self.assertTrue(
            result.acceptance_candidate_verified, result.blockers
        )
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)

    def test_inspection_created_before_completion_denied(self):
        inspection, review = self.prepare()
        inspection.created_at = (
            self.schedule.completed_at - timedelta(seconds=10)
        )
        result = self.verify_with_records(inspection, review)
        self.assert_blocked(result)

    def test_review_persisted_before_inspection_denied(self):
        inspection, review = self.prepare()
        review.created_at = (
            inspection.created_at - timedelta(seconds=10)
        )
        result = self.verify_with_records(inspection, review)
        self.assert_blocked(result)

    def test_inactive_reviewer_invalidates_candidate(self):
        self.prepare()
        User.objects.filter(pk=self.reviewer.pk).update(is_active=False)
        result = verify_post_installation_acceptance(self.project)
        self.assert_blocked(result)

    def test_inactive_inspector_invalidates_candidate(self):
        self.prepare()
        User.objects.filter(pk=self.inspector.pk).update(is_active=False)
        result = verify_post_installation_acceptance(self.project)
        self.assert_blocked(result)
