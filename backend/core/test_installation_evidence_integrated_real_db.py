"""Real database installation readiness and physical review integration."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_installation_combined_real_evidence as fixture_module
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_capture_pending_service import (
    record_pending_physical_inspection,
)
from .equipment_physical_inspection_review_service import (
    review_pending_physical_inspection,
)
from .installation_evidence_integrated_preview import (
    preview_installation_with_physical_reviews,
)
from .models import AuditEvent, ProjectEvidence, Role, User


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealIntegratedInstallationEvidenceTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        self.units = physical_units_from_snapshot(
            msr_id=str(self.msr.pk),
            snapshot=self.msr.snapshot,
        )
        self.assertTrue(self.units)
        self.start = timezone.now() + timedelta(hours=4)
        self.comptroller = User.objects.filter(
            role=Role.COMPTROLLER, is_active=True
        ).first()
        self.assertIsNotNone(self.comptroller)

    def capture(self):
        return record_pending_physical_inspection(
            actor=self.fixture.installation_manager,
            project_id=self.fixture.project.pk,
            msr_id=str(self.msr.pk),
            unit_id=self.units[0].unit_id,
            serial_number="GOODMAN-INTEGRATED-REAL-001",
            captured_at=self.start - timedelta(hours=2),
            installation_starts_at=self.start,
            confirmed_in_person=True,
            inspection_notes="Verified actual identifying label on physical unit.",
        )

    def review(self, pending, accepted):
        return review_pending_physical_inspection(
            actor=self.comptroller,
            pending_id=pending.pk,
            accept_candidate=accepted,
            review_reason="Independent physical-unit review recorded for project.",
            independently_examined=accepted,
        )

    def preview(self):
        return preview_installation_with_physical_reviews(
            project_id=str(self.fixture.project.pk),
            installation_starts_at=self.start,
            now=self.start - timedelta(hours=1),
        )

    def assert_disabled(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)
        self.assertTrue(result.blockers)
        self.assertIsNotNone(result.installation_assessment)

    def test_accepted_real_review_is_counted_but_not_authorized(self):
        pending = self.capture()
        self.review(pending, True)
        counts_before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        result = self.preview()
        counts_after = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        self.assertGreaterEqual(result.total_units, 1)
        self.assertEqual(result.total_units, len(self.units))
        self.assertEqual(result.reviewed_candidate_units, 1)
        self.assertEqual(counts_before, counts_after)
        self.assert_disabled(result)

    def test_real_capture_without_review_is_not_counted(self):
        self.capture()
        result = self.preview()
        self.assertEqual(result.reviewed_candidate_units, 0)
        self.assertFalse(result.all_units_reviewed)
        self.assert_disabled(result)

    def test_real_rejected_review_is_not_counted(self):
        pending = self.capture()
        self.review(pending, False)
        result = self.preview()
        self.assertEqual(result.reviewed_candidate_units, 0)
        self.assertFalse(result.all_units_reviewed)
        self.assert_disabled(result)