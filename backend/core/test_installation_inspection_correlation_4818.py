"""Isolated inspection correlation and FINAL Receipt release safeguards."""
from django.test import TestCase, override_settings

from . import test_receipt_draft_retention_4803 as fixture
from .installation_inspection_correlation_4818 import (
    assess_installation_inspection_candidates,
)
from .installation_completion_evidence_4815 import (
    assess_installation_completion_evidence,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionCorrelation4818(TestCase):
    setUp = fixture.DraftRetentionAcceptance4803.setUp

    def test_unverified_candidates_cannot_grant_acceptance(self):
        candidate = assess_installation_inspection_candidates(self.project)
        self.assertGreater(candidate.physical_unit_count, 0)
        self.assertFalse(candidate.all_candidates_verified)
        self.assertFalse(candidate.post_installation_acceptance_verified)
        self.assertFalse(candidate.trusted_installation_evidence)
        self.assertFalse(candidate.final_receipt_issuance_authorized)

        installation = assess_installation_completion_evidence(self.project)
        self.assertEqual(
            installation.physical_unit_count,
            candidate.physical_unit_count,
        )
        self.assertEqual(
            installation.verified_inspection_candidate_count, 0
        )
        self.assertFalse(installation.trusted_installation_evidence)

        receipt = assess_final_receipt_release_preflight(self.project)
        self.assertFalse(receipt.post_installation_acceptance_verified)
        self.assertFalse(receipt.final_receipt_issuance_authorized)
        self.assertFalse(receipt.customer_delivery_verified)
        self.assertFalse(receipt.completion_authorized)

    def test_correlation_is_read_only(self):
        from .models import ProjectEvidence, AuditEvent

        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        assess_installation_inspection_candidates(self.project)
        assess_installation_completion_evidence(self.project)
        assess_final_receipt_release_preflight(self.project)
        after = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        self.assertEqual(before, after)
