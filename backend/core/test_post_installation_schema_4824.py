"""Post-installation schema and transaction integrity acceptance."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .post_installation_acceptance_4819 import (
    INSPECTION_KIND,
    REVIEW_KIND,
)
from .post_installation_acceptance_verifier_4820 import (
    verify_post_installation_acceptance,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)
from .models import AuditEvent, ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class PostInstallationSchema4824(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def test_evidence_kinds_fit_persisted_field(self):
        field = ProjectEvidence._meta.get_field("kind")
        self.assertEqual(field.max_length, 32)

        for kind in (INSPECTION_KIND, REVIEW_KIND):
            self.assertLessEqual(len(kind), field.max_length)
            self.assertTrue(kind.isascii())

        self.assertNotEqual(INSPECTION_KIND, REVIEW_KIND)

    def test_persisted_kinds_round_trip_and_verify(self):
        inspection = self.capture()
        review = self.review(inspection)

        inspection.refresh_from_db()
        review.refresh_from_db()

        self.assertEqual(inspection.kind, INSPECTION_KIND)
        self.assertEqual(review.kind, REVIEW_KIND)

        evidence = verify_post_installation_acceptance(
            self.project
        )
        self.assertTrue(
            evidence.acceptance_candidate_verified,
            evidence.blockers,
        )
        self.assertFalse(
            evidence.trusted_installation_evidence
        )
        self.assertFalse(
            evidence.final_receipt_issuance_authorized
        )

        receipt = assess_final_receipt_release_preflight(
            self.project
        )
        self.assertTrue(
            receipt.acceptance_candidate_verified
        )
        self.assertFalse(
            receipt.trusted_installation_evidence
        )
        self.assertFalse(
            receipt.final_receipt_issuance_authorized
        )
        self.assertFalse(
            receipt.customer_delivery_verified
        )
        self.assertFalse(
            receipt.completion_authorized
        )

    def test_inspection_audit_failure_rolls_back_record(self):
        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )

        with patch(
            "core.post_installation_acceptance_4819.audit",
            side_effect=RuntimeError("Synthetic audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.capture()

        self.assertEqual(
            before,
            (
                ProjectEvidence.objects.count(),
                AuditEvent.objects.count(),
            ),
        )
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr,
                kind=INSPECTION_KIND,
            ).exists()
        )

    def test_review_audit_failure_rolls_back_decision(self):
        inspection = self.capture()
        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )

        with patch(
            "core.post_installation_acceptance_4819.audit",
            side_effect=RuntimeError("Synthetic audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.review(inspection)

        self.assertEqual(
            before,
            (
                ProjectEvidence.objects.count(),
                AuditEvent.objects.count(),
            ),
        )
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr,
                kind=REVIEW_KIND,
            ).exists()
        )
