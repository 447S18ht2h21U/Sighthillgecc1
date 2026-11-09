"""Database-backed tests for the unregistered physical-capture preview."""
from datetime import timedelta
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone

from .equipment_physical_capture_db_preview import (
    preview_current_msr_physical_capture,
)
from .equipment_physical_units import physical_units_from_snapshot
from .models import AuditEvent, ProjectEvidence
from . import test_installation_combined_real_evidence as evidence_fixture


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealDatabasePhysicalCapturePreviewTests(TestCase):
    def setUp(self):
        fixture = evidence_fixture.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        self.project = fixture.project
        self.units = physical_units_from_snapshot(
            msr_id=str(self.msr.pk),
            snapshot=self.msr.snapshot,
        )
        self.assertTrue(self.units)
        self.now = timezone.now()
        self.values = {
            "project_id": str(self.project.pk),
            "msr_id": str(self.msr.pk),
            "unit_id": self.units[0].unit_id,
            "serial_number": "GOODMAN-REAL-TEST",
            "recorder_id": str(fixture.installation_manager.pk),
            "recorder_role": "INSTALLATION_MANAGER",
            "recorder_active": True,
            "captured_at": self.now,
            "installation_starts_at": self.now + timedelta(hours=1),
        }

    def assess(self, **changes):
        return preview_current_msr_physical_capture(
            **(self.values | changes)
        )

    def test_actual_approved_msr_is_only_candidate(self):
        before = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        result = self.assess()
        after = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        self.assertTrue(result.candidate_valid, result.blockers)
        self.assertEqual(result.unit_id, self.units[0].unit_id)
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)
        self.assertEqual(before, after)

    def test_actual_msr_rejects_unknown_physical_unit(self):
        result = self.assess(unit_id="ROW-999-UNIT-999")
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)

    def test_actual_project_rejects_wrong_msr_identity(self):
        result = self.assess(msr_id=str(uuid4()))
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)