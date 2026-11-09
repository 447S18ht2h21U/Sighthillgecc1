"""Isolated database security tests for pending inspection evidence."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_installation_combined_real_evidence as fixture_module
from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_capture_pending_service import (
    KIND, record_pending_physical_inspection,
)
from .models import AuditEvent, ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class PendingPhysicalInspectionTests(TestCase):
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
        self.now = timezone.now()
        self.values = {
            "actor": fixture.installation_manager,
            "project_id": fixture.project.pk,
            "msr_id": str(self.msr.pk),
            "unit_id": units[0].unit_id,
            "serial_number": "GOODMAN-PHYSICAL-001",
            "captured_at": self.now,
            "installation_starts_at": self.now + timedelta(hours=1),
            "confirmed_in_person": True,
            "inspection_notes": "Unit serial label inspected at the equipment.",
        }

    def record(self, **changes):
        return record_pending_physical_inspection(
            **(self.values | changes)
        )

    def test_authorized_record_is_immutable_and_untrusted(self):
        before = ProjectEvidence.objects.count()
        evidence = self.record()
        self.assertEqual(ProjectEvidence.objects.count(), before + 1)
        self.assertEqual(evidence.kind, KIND)
        self.assertEqual(evidence.digest, canonical_hash(evidence.data))
        self.assertIs(evidence.data["independently_verified"], False)
        self.assertIs(evidence.data["trusted_installation_evidence"], False)
        self.assertIs(evidence.data["installation_authorized"], False)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="equipment.physical_inspection_pending"
            ).exists()
        )

    def test_unauthorized_recorder_cannot_write(self):
        before = ProjectEvidence.objects.count()
        with self.assertRaises(PermissionDenied):
            self.record(actor=self.fixture.sales)
        self.assertEqual(ProjectEvidence.objects.count(), before)

    def test_missing_physical_attestation_denied(self):
        before = ProjectEvidence.objects.count()
        with self.assertRaises(ValidationError):
            self.record(confirmed_in_person=False)
        self.assertEqual(ProjectEvidence.objects.count(), before)

    def test_duplicate_unit_capture_denied(self):
        self.record()
        before = ProjectEvidence.objects.count()
        with self.assertRaises(ValidationError):
            self.record(serial_number="GOODMAN-SECOND-CLAIM")
        self.assertEqual(ProjectEvidence.objects.count(), before)

    def test_audit_failure_rolls_back_evidence(self):
        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        with patch(
            "core.equipment_physical_capture_pending_service.audit",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.record()
        self.assertEqual(
            before,
            (
                ProjectEvidence.objects.count(),
                AuditEvent.objects.count(),
            ),
        )