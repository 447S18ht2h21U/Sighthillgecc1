"""Isolated action-level regressions for equipment-unit review.

The existing immutable review service is mocked; this suite tests
endpoint validation and routing without persisting review decisions.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

# Import the decorated service BEFORE mocking transaction.atomic.
# This avoids intercepting its @transaction.atomic decorator at import.
from . import equipment_physical_capture_pending_service
from . import equipment_physical_inspection_review_service
from .operational_project_api import OperationalProjectViewSet


class EquipmentUnitReviewAPI4877Tests(SimpleTestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.msr_id = str(uuid4())
        self.pending_id = str(uuid4())
        self.reviewer_id = str(uuid4())
        self.recorder_id = str(uuid4())
        self.review_id = str(uuid4())

        self.actor = SimpleNamespace(pk=self.reviewer_id)
        self.msr = SimpleNamespace(
            pk=self.msr_id,
            project_id=self.project_id,
            number=1,
            status="APPROVED",
            snapshot={},
        )
        self.project = SimpleNamespace(
            pk=self.project_id,
            current_approved=self.msr,
            current_approved_id=self.msr_id,
            state="ACTIVE",
        )

        self.data = {
            "purpose": "PHYSICAL_INSPECTION_PENDING_VERIFICATION",
            "project_id": self.project_id,
            "msr_id": self.msr_id,
            "msr_version": 1,
            "snapshot_sha256": "digest",
            "recorded_by": self.recorder_id,
            "confirmed_in_person": True,
            "independently_verified": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
            "unit_id": "ROW-001-UNIT-001",
            "serial_number": "TEST-4877-UNIT",
        }
        self.pending = SimpleNamespace(
            pk=self.pending_id,
            created_by_id=self.recorder_id,
            data=self.data,
            digest="digest",
        )
        self.payload = {
            "pending_id": self.pending_id,
            "accept_candidate": True,
            "review_reason": (
                "Isolated test of independent examination and decision."
            ),
            "independently_examined": True,
        }

        self.view = OperationalProjectViewSet()
        self.view._installation_entry_guard = Mock(return_value=self.actor)
        self.view.get_object = Mock(return_value=self.project)

        pending_queryset = Mock()
        pending_queryset.filter.return_value.first.return_value = self.pending
        self.pending_query = pending_queryset.filter.return_value

        decision_queryset = Mock()
        decision_queryset.exists.return_value = False
        self.decision_query = decision_queryset

        # Patch persistence boundaries, not the authorization logic.
        self.start_patch(
            "core.models.ProjectEvidence.objects.select_for_update",
            return_value=pending_queryset,
        )
        self.start_patch(
            "core.models.ProjectEvidence.objects.filter",
            return_value=decision_queryset,
        )
        self.start_patch(
            "core.documents.canonical_hash",
            return_value="digest",
        )
        self.review_service = self.start_patch(
            "core.equipment_physical_inspection_review_service."
            "review_pending_physical_inspection",
            return_value=SimpleNamespace(pk=self.review_id),
        )
        self.start_patch(
            "django.db.transaction.atomic",
            side_effect=lambda: nullcontext(),
        )

    def start_patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def call_action(self, **updates):
        data = dict(self.payload)
        data.update(updates)
        request = SimpleNamespace(data=data)
        return self.view.review_equipment_unit_inspection(request)

    def test_acceptance_is_internal_only(self):
        response = self.call_action()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["status"], "INTERNAL_CANDIDATE_ACCEPTED"
        )
        for key in (
            "source_authenticated",
            "trusted_installation_evidence",
            "installation_authorized",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(response.data[key], False)
        self.review_service.assert_called_once()

    def test_rejection_remains_explicit_and_untrusted(self):
        response = self.call_action(
            accept_candidate=False,
            independently_examined=False,
        )
        self.assertEqual(response.data["status"], "REJECTED")
        self.assertIs(response.data["completion_authorized"], False)
        self.assertIs(
            self.review_service.call_args.kwargs["accept_candidate"],
            False,
        )

    def test_unauthorized_actor_blocked(self):
        self.view._installation_entry_guard.side_effect = (
            PermissionDenied("Unauthorized")
        )
        with self.assertRaises(PermissionDenied):
            self.call_action()
        self.review_service.assert_not_called()

    def test_acceptance_requires_independent_examination(self):
        with self.assertRaises(ValidationError):
            self.call_action(independently_examined=False)
        self.review_service.assert_not_called()

    def test_self_review_blocked(self):
        self.pending.created_by_id = self.reviewer_id
        self.data["recorded_by"] = self.reviewer_id
        with self.assertRaises(ValidationError):
            self.call_action()
        self.review_service.assert_not_called()

    def test_tampered_evidence_blocked(self):
        self.pending.digest = "incorrect-digest"
        with self.assertRaises(ValidationError):
            self.call_action()
        self.review_service.assert_not_called()

    def test_evidence_from_another_project_blocked(self):
        self.data["project_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.call_action()
        self.review_service.assert_not_called()

    def test_duplicate_review_blocked(self):
        self.decision_query.exists.return_value = True
        with self.assertRaises(ValidationError):
            self.call_action()
        self.review_service.assert_not_called()

    def test_invalid_pending_identifier_blocked(self):
        with self.assertRaises(ValidationError):
            self.call_action(pending_id="not-a-uuid")
        self.review_service.assert_not_called()
