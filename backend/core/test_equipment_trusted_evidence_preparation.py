"""Isolated database checks of the complete preparation workflow."""
from datetime import timedelta
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_installation_combined_real_evidence as fixture_module
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_trusted_evidence_preparation import (
    prepare_physical_equipment_evidence,
)
from .models import AuditEvent, ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class TrustedEvidencePreparationDatabaseTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        units = physical_units_from_snapshot(
            msr_id=str(self.msr.pk),
            snapshot=self.msr.snapshot,
        )
        self.assertTrue(units)
        now = timezone.now()
        self.values = {
            "project_id": str(fixture.project.pk),
            "msr_id": str(self.msr.pk),
            "unit_id": units[0].unit_id,
            "serial_number": "GOODMAN-PREP-001",
            "recorder_id": str(fixture.installation_manager.pk),
            "captured_at": now,
            "installation_starts_at": now + timedelta(hours=1),
        }

    def prepare(self, **changes):
        return prepare_physical_equipment_evidence(
            **(self.values | changes)
        )

    def assert_untrusted(self, result):
        self.assertFalse(result.trusted_evidence_created)
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)

    def test_valid_real_records_complete_preparation_only(self):
        before = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        result = self.prepare()
        after = (
            AuditEvent.objects.count(),
            ProjectEvidence.objects.count(),
        )
        self.assertTrue(result.preparation_complete, result.blockers)
        self.assertEqual(result.normalized_serial, "GOODMAN-PREP-001")
        self.assertEqual(before, after)
        self.assert_untrusted(result)

    def test_real_unauthorized_recorder_denied(self):
        result = self.prepare(
            recorder_id=str(self.fixture.sales.pk)
        )
        self.assertFalse(result.preparation_complete)
        self.assertTrue(result.blockers)
        self.assert_untrusted(result)

    def test_real_wrong_approved_msr_denied(self):
        result = self.prepare(msr_id=str(uuid4()))
        self.assertFalse(result.preparation_complete)
        self.assertTrue(result.blockers)
        self.assert_untrusted(result)

    def test_unknown_physical_unit_denied(self):
        result = self.prepare(unit_id="ROW-999-UNIT-999")
        self.assertFalse(result.preparation_complete)
        self.assertTrue(result.blockers)
        self.assert_untrusted(result)