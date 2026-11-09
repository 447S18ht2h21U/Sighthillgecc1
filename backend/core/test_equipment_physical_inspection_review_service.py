"""Database tests for independent review, denial, and audit rollback."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_installation_combined_real_evidence as fixture_module
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_capture_pending_service import (
    record_pending_physical_inspection,
)
from .equipment_physical_inspection_review_service import (
    REVIEW_KIND, review_pending_physical_inspection,
)
from .documents import canonical_hash
from .models import AuditEvent, ProjectEvidence
from django.utils import timezone
from datetime import timedelta


@override_settings(DEBUG=True, ENVIRONMENT="development")
class IndependentPhysicalInspectionReviewTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        msr = fixture.prepare()
        units = physical_units_from_snapshot(
            msr_id=str(msr.pk), snapshot=msr.snapshot
        )
        now = timezone.now()
        self.pending = record_pending_physical_inspection(
            actor=fixture.installation_manager,
            project_id=fixture.project.pk,
            msr_id=str(msr.pk),
            unit_id=units[0].unit_id,
            serial_number="GOODMAN-REVIEW-001",
            captured_at=now,
            installation_starts_at=now + timedelta(hours=1),
            confirmed_in_person=True,
            inspection_notes="I physically checked the identifying serial label.",
        )
        self.values = {
            "actor": fixture.manager,
            "pending_id": self.pending.pk,
            "accept_candidate": True,
            "review_reason": "Independent review of this physical-unit inspection.",
            "independently_examined": True,
        }
        # Use an existing Comptroller fixture account if present.
        from .models import Role, User
        reviewers = list(User.objects.filter(role=Role.COMPTROLLER, is_active=True))
        if not reviewers:
            self.fail("Foundation fixture requires an active Comptroller.")
        self.values["actor"] = reviewers[0]

    def review(self, **changes):
        return review_pending_physical_inspection(
            **(self.values | changes)
        )

    def test_favorable_review_remains_untrusted(self):
        decision = self.review()
        self.assertEqual(decision.kind, REVIEW_KIND)
        self.assertEqual(decision.data["status"], "CANDIDATE_ACCEPTED")
        self.assertEqual(decision.digest, canonical_hash(decision.data))
        self.assertIs(decision.data["trusted_installation_evidence"], False)
        self.assertIs(decision.data["installation_authorized"], False)
        self.assertTrue(AuditEvent.objects.filter(
            action="equipment.physical_inspection_reviewed"
        ).exists())

    def test_rejection_is_immutable_review_record(self):
        decision = self.review(
            accept_candidate=False,
            independently_examined=False,
        )
        self.assertEqual(decision.data["status"], "REJECTED")
        self.assertFalse(decision.data["trusted_installation_evidence"])

    def test_recorder_cannot_review_their_own_claim(self):
        before = ProjectEvidence.objects.count()
        with self.assertRaises(PermissionDenied):
            self.review(actor=self.fixture.installation_manager)
        self.assertEqual(ProjectEvidence.objects.count(), before)

    def test_duplicate_decision_rejected(self):
        self.review()
        before = ProjectEvidence.objects.count()
        with self.assertRaises(ValidationError):
            self.review()
        self.assertEqual(ProjectEvidence.objects.count(), before)

    def test_audit_failure_rolls_back_review(self):
        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        with patch(
            "core.equipment_physical_inspection_review_service.audit",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.review()
        self.assertEqual(
            before,
            (
                ProjectEvidence.objects.count(),
                AuditEvent.objects.count(),
            ),
        )