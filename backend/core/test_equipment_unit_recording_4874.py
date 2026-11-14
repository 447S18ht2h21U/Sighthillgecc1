"""Isolated behavioral tests for the pending equipment-unit endpoint.

Mocks the existing persistence service so these tests never record
an inspection or promote synthetic evidence into trusted evidence.
"""
from datetime import timedelta
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .operational_project_api import OperationalProjectViewSet


class EquipmentUnitRecording4874Tests(SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()
        self.start = self.now - timedelta(days=1)
        self.capture = self.start - timedelta(minutes=30)

        self.actor = SimpleNamespace(pk="assigned-manager")
        self.msr = SimpleNamespace(
            pk="approved-msr",
            project_id="project-1",
            status="APPROVED",
        )
        self.project = SimpleNamespace(
            pk="project-1",
            current_approved=self.msr,
            current_approved_id=self.msr.pk,
            state="ACTIVE",
        )
        self.schedule = SimpleNamespace(
            installation_manager_id=self.actor.pk,
            cancelled_at=None,
            scheduled_date=timezone.localtime(self.start).date(),
        )

        self.payload = {
            "msr_id": self.msr.pk,
            "unit_id": "ROW-001-UNIT-001",
            "serial_number": "UNIT-TEST-SERIAL-001",
            "captured_at": self.capture.isoformat(),
            "installation_starts_at": self.start.isoformat(),
            "confirmed_in_person": True,
            "inspection_notes": (
                "Isolated unit-test inspection claim; "
                "no physical inspection performed."
            ),
        }

        self.view = OperationalProjectViewSet()
        self.view._installation_entry_guard = Mock(
            return_value=self.actor
        )
        self.view.get_object = Mock(return_value=self.project)

        self.schedule_query = Mock()
        self.schedule_query.filter.return_value = [self.schedule]

        self.schedule_patch = patch(
            "core.models.InstallationSchedule.objects.select_for_update",
            return_value=self.schedule_query,
        )
        self.atomic_patch = patch(
            "django.db.transaction.atomic",
            side_effect=lambda: nullcontext(),
        )
        self.record_patch = patch(
            "core.equipment_physical_capture_pending_service."
            "record_pending_physical_inspection",
            return_value=SimpleNamespace(pk="pending-evidence-1"),
        )

        # Import and patch the existing decorated service before
        # temporarily mocking transaction.atomic for this test.
        # Otherwise the mock intercepts @transaction.atomic at import.
        self.schedule_patch.start()
        self.record_service = self.record_patch.start()
        self.atomic_patch.start()
        self.addCleanup(self.schedule_patch.stop)
        self.addCleanup(self.atomic_patch.stop)
        self.addCleanup(self.record_patch.stop)

    def call_endpoint(self, **updates):
        payload = dict(self.payload)
        payload.update(updates)
        request = SimpleNamespace(data=payload)
        return self.view.record_equipment_unit_inspection(request)

    def test_valid_claim_remains_pending_and_untrusted(self):
        response = self.call_endpoint()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["status"], "PENDING_INDEPENDENT_REVIEW"
        )
        for field in (
            "source_authenticated",
            "trusted_installation_evidence",
            "installation_authorized",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(response.data[field], False)
        self.record_service.assert_called_once()

    def test_role_guard_blocks_recording(self):
        self.view._installation_entry_guard.side_effect = (
            PermissionDenied("Unauthorized")
        )
        with self.assertRaises(PermissionDenied):
            self.call_endpoint()
        self.record_service.assert_not_called()

    def test_in_person_attestation_is_mandatory(self):
        with self.assertRaises(ValidationError):
            self.call_endpoint(confirmed_in_person=False)
        self.record_service.assert_not_called()

    def test_future_observation_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.call_endpoint(
                captured_at=(self.now + timedelta(days=1)).isoformat()
            )
        self.record_service.assert_not_called()

    def test_wrong_schedule_assignment_is_rejected(self):
        self.schedule.installation_manager_id = "another-manager"
        with self.assertRaises(ValidationError):
            self.call_endpoint()
        self.record_service.assert_not_called()

    def test_wrong_approved_msr_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.call_endpoint(msr_id="different-msr")
        self.record_service.assert_not_called()

    def test_duplicate_evidence_rejection_is_propagated(self):
        self.record_service.side_effect = ValidationError(
            "Duplicate unit or serial inspection."
        )
        with self.assertRaises(ValidationError):
            self.call_endpoint()
        self.record_service.assert_called_once()

    def test_wrong_installation_start_date_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.call_endpoint(
                installation_starts_at=(
                    self.start + timedelta(days=3)
                ).isoformat()
            )
        self.record_service.assert_not_called()
