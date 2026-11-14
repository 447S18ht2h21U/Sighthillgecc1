"""Read-only, mocked behavioral checks for equipment review queue."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied

from .equipment_physical_capture_pending_service import KIND as PENDING_KIND
from .equipment_physical_inspection_review_service import REVIEW_KIND
from .operational_project_api import OperationalProjectViewSet


class EquipmentUnitQueue4879Tests(SimpleTestCase):
    def setUp(self):
        self.project_id = "project-4879"
        self.msr_id = "msr-4879"
        self.pending_id = "pending-4879"
        self.recorder_id = "manager-4879"

        self.msr = SimpleNamespace(
            pk=self.msr_id,
            project_id=self.project_id,
            number=1,
            status="APPROVED",
            snapshot={"equipment": []},
        )
        self.project = SimpleNamespace(
            pk=self.project_id,
            current_approved=self.msr,
            current_approved_id=self.msr_id,
            state="ACTIVE",
        )
        self.unit = SimpleNamespace(
            unit_id="ROW-001-UNIT-001",
            brand="Goodman",
            model_number="MODEL-4879",
        )
        self.payload = {
            "purpose": "PHYSICAL_INSPECTION_PENDING_VERIFICATION",
            "project_id": self.project_id,
            "msr_id": self.msr_id,
            "msr_version": 1,
            "snapshot_sha256": "digest-4879",
            "unit_id": self.unit.unit_id,
            "recorded_by": self.recorder_id,
            "confirmed_in_person": True,
            "independently_verified": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
            "serial_number": "SIMULATED-SERIAL-4879",
            "inspection_notes": "Synthetic test evidence only, not a real inspection.",
            "captured_at": "2026-11-14T09:00:00-05:00",
        }
        self.pending = SimpleNamespace(
            pk=self.pending_id,
            created_by_id=self.recorder_id,
            digest="digest-4879",
            data=self.payload,
        )
        self.pendings = [self.pending]
        self.reviews = []

        self.view = OperationalProjectViewSet()
        self.view._installation_entry_guard = Mock(
            return_value=SimpleNamespace(pk="comptroller-4879")
        )
        self.view.get_object = Mock(return_value=self.project)

        self.start_patch(
            "core.equipment_physical_units.physical_units_from_snapshot",
            return_value=(self.unit,),
        )
        self.start_patch(
            "core.documents.canonical_hash",
            return_value="digest-4879",
        )

        def records(*args, **kwargs):
            if kwargs.get("kind") == PENDING_KIND:
                return list(self.pendings)
            if kwargs.get("kind") == REVIEW_KIND:
                return list(self.reviews)
            raise AssertionError("Unexpected evidence query.")

        self.start_patch(
            "core.models.ProjectEvidence.objects.filter",
            side_effect=records,
        )

    def start_patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def read_queue(self):
        return self.view.equipment_unit_review_queue(
            SimpleNamespace()
        )

    def assert_no_authority(self, response):
        for field in (
            "source_authenticated",
            "trusted_installation_evidence",
            "installation_authorized",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(response.data[field], False)
        self.assertIs(response.data["read_only"], True)

    def test_valid_pending_evidence_visible_to_comptroller(self):
        response = self.read_queue()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "QUEUE_AVAILABLE")
        item = response.data["units"][0]
        self.assertEqual(item["status"], "PENDING_INDEPENDENT_REVIEW")
        self.assertEqual(item["pending_id"], self.pending_id)
        self.assert_no_authority(response)

    def test_missing_inspection_stays_missing(self):
        self.pendings.clear()
        response = self.read_queue()
        self.assertEqual(response.data["units"][0]["status"], "NO_INSPECTION")
        self.assertIsNone(response.data["units"][0]["pending_id"])
        self.assert_no_authority(response)

    def test_tampered_inspection_is_invalid(self):
        self.pending.digest = "incorrect"
        response = self.read_queue()
        self.assertEqual(response.data["units"][0]["status"], "EVIDENCE_INVALID")
        self.assertIsNone(response.data["units"][0]["pending_id"])
        self.assert_no_authority(response)

    def test_duplicate_unit_inspections_are_invalid(self):
        self.pendings.append(SimpleNamespace(
            pk="duplicate",
            created_by_id=self.recorder_id,
            digest="digest-4879",
            data=dict(self.payload),
        ))
        response = self.read_queue()
        self.assertEqual(response.data["units"][0]["status"], "EVIDENCE_INVALID")
        self.assert_no_authority(response)

    def test_existing_review_is_not_treated_as_approved(self):
        self.reviews.append(SimpleNamespace(
            data={"pending_id": self.pending_id},
        ))
        response = self.read_queue()
        self.assertEqual(
            response.data["units"][0]["status"],
            "REVIEW_RECORDED_UNVERIFIED",
        )
        self.assertIsNone(response.data["units"][0]["pending_id"])
        self.assert_no_authority(response)

    def test_unavailable_inventory_fails_closed(self):
        self.project.current_approved = None
        response = self.read_queue()
        self.assertEqual(response.data["status"], "INVENTORY_UNAVAILABLE")
        self.assertEqual(response.data["units"], [])
        self.assert_no_authority(response)

    def test_unauthorized_user_cannot_read_queue(self):
        self.view._installation_entry_guard.side_effect = (
            PermissionDenied("Unauthorized")
        )
        with self.assertRaises(PermissionDenied):
            self.read_queue()
