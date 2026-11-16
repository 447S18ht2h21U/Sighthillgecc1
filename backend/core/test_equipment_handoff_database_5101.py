"""Disposable database regression for the physical-equipment handoff.

All records are synthetic. The approved equipment snapshot is populated
as a test fixture only, after normal approval of the baseline MSR.
Only the upstream physical-equipment preparation prerequisite is mocked.
"""

from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .documents import canonical_hash
from .equipment_physical_capture_pending_service import (
    KIND as PENDING_KIND,
    record_pending_physical_inspection,
)
from .equipment_physical_inspection_review_service import (
    REVIEW_KIND,
    review_pending_physical_inspection,
)
from .models import MSR, ProjectEvidence, Role, User
from .operational_project_api import OperationalProjectViewSet
from . import tests as foundation_module


@override_settings(DEBUG=True, ENVIRONMENT="development")
class EquipmentHandoffDatabase5101Tests(TestCase):
    def setUp(self):
        foundation_module.FoundationTests.setUp(self)

        self.installer = User.objects.create_user(
            username="handoff-installer-5101",
            password=None,
            role=Role.INSTALLATION_MANAGER,
            initials="HI",
        )

        # Construct an approved-state fixture from an existing DRAFT.
        # This does NOT test the MSR approval workflow. It never edits
        # an already-approved MSR and must never be used operationally.
        self.msr = self.project.pending
        if self.msr.status != "DRAFT":
            raise RuntimeError("STOP: Expected draft test MSR.")

        snapshot = deepcopy(self.msr.snapshot)
        snapshot["equipment"] = [{
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Synthetic isolated handoff equipment",
            "quantity": 1,
            "category_of_work": "New installation",
        }]
        # One fixture-only transition while the record is still DRAFT.
        # No change to an existing APPROVED record is attempted.
        MSR.objects.filter(
            pk=self.msr.pk, status="DRAFT"
        ).update(
            snapshot=snapshot,
            status="APPROVED",
            approved_by=self.comptroller,
            approved_at=timezone.now(),
        )
        self.project.current_approved = self.msr
        self.project.pending = None
        self.project.save(update_fields=["current_approved", "pending"])
        self.msr.refresh_from_db()
        self.project.refresh_from_db()

        self.assertEqual(
            self.project.current_approved_id, self.msr.pk
        )

        self.unit_id = "ROW-001-UNIT-001"
        self.serial = "SYNTHETIC-5101-NOT-A-REAL-SERIAL"

        self.view = OperationalProjectViewSet()
        self.view.get_object = Mock(return_value=self.project)
        self.view._equipment_unit_review_read_guard = Mock(
            return_value=self.comptroller
        )

    def record_claim(self):
        captured = timezone.now() - timedelta(hours=2)
        installation_starts = captured + timedelta(minutes=30)

        prepared = SimpleNamespace(
            preparation_complete=True,
            blockers=(),
            msr_id=str(self.msr.pk),
            unit_id=self.unit_id,
            normalized_serial=self.serial,
        )

        with patch(
            "core.equipment_physical_capture_pending_service."
            "prepare_physical_equipment_evidence",
            return_value=prepared,
        ) as preparation:
            record = record_pending_physical_inspection(
                actor=self.installer,
                project_id=self.project.pk,
                msr_id=str(self.msr.pk),
                unit_id=self.unit_id,
                serial_number=self.serial,
                captured_at=captured,
                installation_starts_at=installation_starts,
                confirmed_in_person=True,
                inspection_notes=(
                    "Synthetic database regression only; "
                    "no actual equipment was inspected."
                ),
            )

        preparation.assert_called_once()
        record.refresh_from_db()
        return record

    def queue(self):
        return self.view.equipment_unit_review_queue(
            SimpleNamespace()
        )

    def assert_queue_untrusted(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["read_only"], True)
        for field in (
            "source_authenticated",
            "trusted_installation_evidence",
            "installation_authorized",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(response.data[field], False)

    def test_persisted_capture_queue_and_independent_review(self):
        pending = self.record_claim()
        self.assertEqual(pending.kind, PENDING_KIND)
        self.assertEqual(pending.created_by_id, self.installer.pk)
        self.assertEqual(
            pending.digest, canonical_hash(pending.data)
        )
        self.assertIs(
            pending.data["trusted_installation_evidence"], False
        )

        queued = self.queue()
        self.assert_queue_untrusted(queued)
        self.assertEqual(queued.data["status"], "QUEUE_AVAILABLE")
        self.assertEqual(len(queued.data["units"]), 1)
        self.assertEqual(
            queued.data["units"][0]["status"],
            "PENDING_INDEPENDENT_REVIEW",
        )
        self.assertEqual(
            queued.data["units"][0]["pending_id"],
            str(pending.pk),
        )

        with self.assertRaises(ValidationError):
            self.record_claim()

        with self.assertRaises(ValidationError):
            review_pending_physical_inspection(
                actor=self.comptroller,
                pending_id=pending.pk,
                accept_candidate=True,
                review_reason="Synthetic review without examination.",
                independently_examined=False,
            )

        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=REVIEW_KIND
            ).exists()
        )

        reviewed = review_pending_physical_inspection(
            actor=self.comptroller,
            pending_id=pending.pk,
            accept_candidate=True,
            review_reason=(
                "Synthetic isolated independent review decision."
            ),
            independently_examined=True,
        )
        reviewed.refresh_from_db()

        self.assertEqual(reviewed.kind, REVIEW_KIND)
        self.assertNotEqual(
            reviewed.created_by_id, pending.created_by_id
        )
        self.assertEqual(
            reviewed.data["status"], "CANDIDATE_ACCEPTED"
        )
        self.assertEqual(
            reviewed.data["pending_id"], str(pending.pk)
        )
        self.assertEqual(
            reviewed.digest, canonical_hash(reviewed.data)
        )
        self.assertIs(
            reviewed.data["trusted_installation_evidence"], False
        )
        self.assertIs(
            reviewed.data["installation_authorized"], False
        )

        after = self.queue()
        self.assert_queue_untrusted(after)
        self.assertEqual(
            after.data["units"][0]["status"],
            "REVIEW_RECORDED_UNVERIFIED",
        )
        self.assertIsNone(after.data["units"][0]["pending_id"])

        with self.assertRaises(ValidationError):
            review_pending_physical_inspection(
                actor=self.comptroller,
                pending_id=pending.pk,
                accept_candidate=True,
                review_reason="Duplicate synthetic review prohibited.",
                independently_examined=True,
            )

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=PENDING_KIND
            ).count(), 1
        )
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=REVIEW_KIND
            ).count(), 1
        )

    def test_persisted_tampering_fails_closed(self):
        """Database immutability prevents inspection evidence updates."""
        from django.db import IntegrityError, transaction

        pending = self.record_claim()
        original_data = dict(pending.data)
        original_digest = pending.digest

        altered = dict(original_data)
        altered["purpose"] = "TAMPERED_SYNTHETIC_TEST"

        # An inner transaction savepoint isolates the intentionally
        # rejected update, leaving the outer TestCase transaction usable.
        with self.assertRaisesRegex(
            IntegrityError, "Release evidence is immutable"
        ):
            with transaction.atomic():
                ProjectEvidence.objects.filter(pk=pending.pk).update(
                    data=altered
                )

        pending.refresh_from_db()
        self.assertEqual(pending.data, original_data)
        self.assertEqual(pending.digest, original_digest)
        self.assertEqual(
            pending.digest, canonical_hash(pending.data)
        )

        queued = self.queue()
        self.assert_queue_untrusted(queued)
        self.assertEqual(
            queued.data["units"][0]["status"],
            "PENDING_INDEPENDENT_REVIEW",
        )
        self.assertEqual(
            queued.data["units"][0]["pending_id"],
            str(pending.pk),
        )

        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=REVIEW_KIND
            ).exists()
        )

    def test_pending_review_cannot_unlock_completion(self):
        """Persisted claims and internal review cannot release a project."""
        from rest_framework.exceptions import ValidationError
        from .equipment_trust_verifier_4785 import (
            verify_equipment_trust_decisions,
        )
        from .installation_completion_evidence_4815 import (
            assess_installation_completion_evidence,
        )
        from .final_receipt_adjudication_readiness_4789 import (
            assess_final_receipt_adjudication_readiness,
        )

        pending = self.record_claim()

        gates = (
            (
                "equipment trust",
                verify_equipment_trust_decisions,
                ("trusted_installation_evidence",
                 "installation_authorized",
                 "receipt_issuance_authorized",
                 "customer_delivery_verified",
                 "completion_authorized"),
            ),
            (
                "installation completion",
                assess_installation_completion_evidence,
                ("trusted_installation_evidence",
                 "final_receipt_issuance_authorized",
                 "customer_delivery_verified",
                 "completion_authorized"),
            ),
            (
                "final receipt",
                assess_final_receipt_adjudication_readiness,
                ("trusted_installation_evidence",
                 "installation_authorized",
                 "final_receipt_issuance_authorized",
                 "customer_delivery_verified",
                 "completion_authorized"),
            ),
        )

        for stage in ("PENDING", "INTERNALLY_REVIEWED"):
            if stage == "INTERNALLY_REVIEWED":
                review = review_pending_physical_inspection(
                    actor=self.comptroller,
                    pending_id=pending.pk,
                    accept_candidate=True,
                    review_reason=(
                        "Synthetic independent review without authority."
                    ),
                    independently_examined=True,
                )
                review.refresh_from_db()
                self.assertEqual(
                    review.data["status"], "CANDIDATE_ACCEPTED"
                )
                self.assertIs(
                    review.data["trusted_installation_evidence"], False
                )

            queued = self.queue()
            self.assert_queue_untrusted(queued)
            self.assertEqual(
                queued.data["units"][0]["status"],
                "PENDING_INDEPENDENT_REVIEW"
                if stage == "PENDING"
                else "REVIEW_RECORDED_UNVERIFIED",
            )

            for name, assessor, fields in gates:
                with self.subTest(stage=stage, gate=name):
                    try:
                        result = assessor(self.project)
                    except (ValueError, ValidationError):
                        # Rejection of an unmet prerequisite is fail-closed.
                        continue

                    self.assertEqual(
                        str(result.project_id), str(self.project.pk)
                    )
                    for field in fields:
                        self.assertIs(
                            getattr(result, field), False,
                            f"{stage}: {name} elevated {field}",
                        )
                    self.assertTrue(
                        result.blockers,
                        f"{stage}: {name} had no blockers",
                    )
                    if name == "equipment trust":
                        self.assertIs(
                            result.all_approval_decisions_verified, False
                        )

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=PENDING_KIND
            ).count(), 1
        )
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=REVIEW_KIND
            ).count(), 1
        )
