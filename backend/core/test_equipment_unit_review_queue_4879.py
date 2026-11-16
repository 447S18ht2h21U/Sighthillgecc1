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

    def test_record_queue_review_handoff_remains_untrusted(self):
        """Cross-endpoint handoff with synthetic, nonpersistent evidence."""
        from contextlib import nullcontext
        from datetime import timedelta
        from uuid import uuid4
        from django.utils import timezone
        from rest_framework.exceptions import ValidationError
        from .models import Role

        pending_id = str(uuid4())
        recorder = SimpleNamespace(pk=self.recorder_id)
        reviewer = SimpleNamespace(pk="comptroller-4879")

        self.pending.pk = pending_id
        self.pending_id = pending_id
        self.pendings.clear()
        self.reviews.clear()

        started = timezone.now() - timedelta(days=1)
        captured = started - timedelta(minutes=30)

        schedule = SimpleNamespace(
            installation_manager_id=recorder.pk,
            cancelled_at=None,
            scheduled_date=timezone.localtime(started).date(),
        )
        schedule_query = Mock()
        schedule_query.filter.return_value = [schedule]

        payload = {
            "msr_id": self.msr_id,
            "unit_id": self.unit.unit_id,
            "serial_number": self.payload["serial_number"],
            "captured_at": captured.isoformat(),
            "installation_starts_at": started.isoformat(),
            "confirmed_in_person": True,
            "inspection_notes": self.payload["inspection_notes"],
        }

        authority_fields = (
            "source_authenticated",
            "trusted_installation_evidence",
            "installation_authorized",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        )

        def assert_action_untrusted(response):
            for field in authority_fields:
                self.assertIn(field, response.data)
                self.assertIs(response.data[field], False)

        def guard(request, role):
            if role == Role.INSTALLATION_MANAGER:
                return recorder
            if role == Role.COMPTROLLER:
                return reviewer
            raise AssertionError("Unexpected authorization role.")

        self.view._installation_entry_guard.side_effect = guard

        def capture(**kwargs):
            self.assertEqual(kwargs["actor"].pk, recorder.pk)
            self.assertEqual(kwargs["unit_id"], self.unit.unit_id)
            self.assertTrue(kwargs["confirmed_in_person"])
            self.pendings.append(self.pending)
            return self.pending

        pending_query = Mock()
        pending_query.filter.return_value.first.return_value = self.pending

        def evidence_records(*args, **kwargs):
            kind = kwargs.get("kind")
            if kind == PENDING_KIND:
                return list(self.pendings)
            if kind == REVIEW_KIND:
                if "data__pending_id" in kwargs:
                    query = Mock()
                    query.exists.return_value = bool(self.reviews)
                    return query
                return list(self.reviews)
            raise AssertionError("Unexpected evidence query.")

        def review(**kwargs):
            self.assertEqual(kwargs["actor"].pk, reviewer.pk)
            self.assertEqual(str(kwargs["pending_id"]), pending_id)
            record = SimpleNamespace(
                pk=str(uuid4()),
                data={
                    "pending_id": pending_id,
                    "unit_id": self.unit.unit_id,
                },
            )
            self.reviews.append(record)
            return record

        with (
            patch(
                "core.models.InstallationSchedule.objects.select_for_update",
                return_value=schedule_query,
            ),
            patch(
                "core.models.ProjectEvidence.objects.select_for_update",
                return_value=pending_query,
            ),
            patch(
                "core.models.ProjectEvidence.objects.filter",
                side_effect=evidence_records,
            ),
            patch(
                "core.equipment_physical_capture_pending_service."
                "record_pending_physical_inspection",
                side_effect=capture,
            ) as capture_service,
            patch(
                "core.equipment_physical_inspection_review_service."
                "review_pending_physical_inspection",
                side_effect=review,
            ) as review_service,
            patch(
                "django.db.transaction.atomic",
                side_effect=lambda: nullcontext(),
            ),
        ):
            recorded = self.view.record_equipment_unit_inspection(
                SimpleNamespace(data=payload)
            )
            self.assertEqual(recorded.status_code, 201)
            self.assertEqual(
                recorded.data["status"],
                "PENDING_INDEPENDENT_REVIEW",
            )
            assert_action_untrusted(recorded)
            capture_service.assert_called_once()
            self.assertEqual(len(self.pendings), 1)

            queued = self.read_queue()
            self.assertEqual(queued.status_code, 200)
            self.assertEqual(
                queued.data["units"][0]["status"],
                "PENDING_INDEPENDENT_REVIEW",
            )
            self.assertEqual(
                queued.data["units"][0]["pending_id"],
                pending_id,
            )
            self.assert_no_authority(queued)

            decision = {
                "pending_id": pending_id,
                "accept_candidate": True,
                "review_reason": (
                    "Synthetic independent review regression only."
                ),
                "independently_examined": True,
            }

            self.view._installation_entry_guard.side_effect = (
                lambda request, role: recorder
            )
            with self.assertRaises(ValidationError):
                self.view.review_equipment_unit_inspection(
                    SimpleNamespace(data=decision)
                )
            review_service.assert_not_called()

            self.view._installation_entry_guard.side_effect = guard

            with self.assertRaises(ValidationError):
                self.view.review_equipment_unit_inspection(
                    SimpleNamespace(data={
                        **decision,
                        "independently_examined": False,
                    })
                )
            review_service.assert_not_called()

            reviewed = self.view.review_equipment_unit_inspection(
                SimpleNamespace(data=decision)
            )
            self.assertEqual(reviewed.status_code, 201)
            self.assertEqual(
                reviewed.data["status"],
                "INTERNAL_CANDIDATE_ACCEPTED",
            )
            assert_action_untrusted(reviewed)
            review_service.assert_called_once()

            with self.assertRaises(ValidationError):
                self.view.review_equipment_unit_inspection(
                    SimpleNamespace(data=decision)
                )
            review_service.assert_called_once()

            after = self.read_queue()
            self.assertEqual(
                after.data["units"][0]["status"],
                "REVIEW_RECORDED_UNVERIFIED",
            )
            self.assertIsNone(after.data["units"][0]["pending_id"])
            self.assert_no_authority(after)

            original = self.pending.data["purpose"]
            try:
                self.pending.data["purpose"] = "TAMPERED_TEST_CLAIM"
                corrupted = self.read_queue()
                self.assertEqual(
                    corrupted.data["units"][0]["status"],
                    "EVIDENCE_INVALID",
                )
                self.assert_no_authority(corrupted)
            finally:
                self.pending.data["purpose"] = original
