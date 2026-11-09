"""Isolated database regressions for synthetic serial capture."""
from unittest.mock import patch

from django.test import override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_serial_capture_service import (
    SERIAL_KIND, capture_synthetic_serial,
)
from .models import AuditEvent, ProjectEvidence
from .test_equipment_serial_exception_service import (
    SerialExceptionRequestServiceTests,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class SerialCaptureServiceTests(SerialExceptionRequestServiceTests):
    def capture(self, msr, **changes):
        arguments = {
            "actor": self.installation_manager,
            "project_id": self.project.pk,
            "msr_id": msr.pk,
            "unit_id": "ROW-001-UNIT-001",
            "serial_number": "GOODMAN-UNIT-001",
        }
        arguments.update(changes)
        return capture_synthetic_serial(**arguments)

    def test_serial_capture_is_immutable_and_audited(self):
        msr = self.prepare()
        evidence = self.capture(msr)
        self.assertEqual(evidence.kind, SERIAL_KIND)
        self.assertEqual(evidence.data["serial_number"], "GOODMAN-UNIT-001")
        self.assertFalse(evidence.data["trusted_installation_evidence"])
        self.assertFalse(evidence.data["installation_authorized"])
        self.assertEqual(evidence.digest, canonical_hash(evidence.data))
        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.serial_captured_synthetic"
            ).count(), 1
        )

    def test_sales_manager_cannot_capture_serial(self):
        msr = self.prepare()
        with self.assertRaises(PermissionDenied):
            self.capture(msr, actor=self.manager)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=SERIAL_KIND).exists()
        )

    def test_unknown_physical_unit_is_rejected(self):
        msr = self.prepare()
        with self.assertRaises(ValidationError):
            self.capture(msr, unit_id="ROW-009-UNIT-001")
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=SERIAL_KIND).exists()
        )

    def test_second_capture_for_same_unit_is_rejected(self):
        msr = self.prepare()
        self.capture(msr)
        with self.assertRaises(ValidationError):
            self.capture(msr, serial_number="GOODMAN-REPLACEMENT")
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=SERIAL_KIND).count(), 1
        )

    def test_duplicate_serial_across_units_is_rejected(self):
        msr = self.prepare()
        self.capture(msr)
        with self.assertRaises(ValidationError):
            self.capture(
                msr,
                unit_id="ROW-001-UNIT-002",
                serial_number="goodman-unit-001",
            )
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=SERIAL_KIND).count(), 1
        )

    def test_serial_capture_audit_failure_rolls_back(self):
        msr = self.prepare()
        with patch(
            "core.equipment_serial_capture_service.audit",
            side_effect=RuntimeError("synthetic serial audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic serial audit failure"
            ):
                self.capture(msr)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=SERIAL_KIND).exists()
        )