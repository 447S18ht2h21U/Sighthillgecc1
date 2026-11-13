"""Disposable SQLite acceptance of equipment trust adjudication.

Real immutable evidence records, users, Project and MSR.
The reviewed manifest is a controlled fixture. No live authority.
"""

import os
from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch

from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_trust_decision_4784 import (
    KIND,
    record_equipment_trust_decision,
)
from .equipment_trust_verifier_4785 import (
    verify_equipment_trust_decisions,
)
from .models import ProjectEvidence, Role, User
from .receipt_equipment_manifest_4768 import (
    ReceiptEquipmentManifest,
    ReviewedEquipmentUnit,
)
from . import test_final_receipt_retention_4773 as fixture_module


WRITER = "core.equipment_trust_decision_4784"
READER = "core.equipment_trust_verifier_4785"
PENDING_KIND = "PHYSICAL_UNIT_CAPTURE_PENDING"
REVIEW_KIND = "PHYSICAL_INSPECTION_REVIEW"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class EquipmentTrustDatabaseAcceptance4786(TestCase):
    setUp = fixture_module.InternalReceiptDatabaseAcceptance4773.setUp

    def prepare(self):
        self.installer = User.objects.create_user(
            username="equipment-installer-4786",
            password=None,
            role=Role.INSTALLATION_MANAGER,
            initials="EI",
        )

        self.ceo = User.objects.create_user(
            username="equipment-ceo-4786",
            password=None,
            role=Role.CEO,
            initials="EC",
        )

        self.unit_id = "ROW-001-UNIT-001"
        self.serial = "SERIAL-4786"
        snapshot_hash = canonical_hash(self.msr.snapshot)

        capture_data = {
            "purpose": "PHYSICAL_INSPECTION_PENDING_VERIFICATION",
            "project_id": str(self.project.pk),
            "msr_id": str(self.msr.pk),
            "msr_version": self.msr.number,
            "snapshot_sha256": snapshot_hash,
            "unit_id": self.unit_id,
            "serial_number": self.serial,
            "recorded_by": str(self.installer.pk),
            "confirmed_in_person": True,
            "independently_verified": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
        }

        self.capture = ProjectEvidence.objects.create(
            msr=self.msr,
            kind=PENDING_KIND,
            created_by=self.installer,
            data=capture_data,
            digest=canonical_hash(capture_data),
        )

        review_data = {
            "status": "CANDIDATE_ACCEPTED",
            "pending_id": str(self.capture.pk),
            "pending_digest": self.capture.digest,
            "project_id": str(self.project.pk),
            "msr_id": str(self.msr.pk),
            "msr_version": self.msr.number,
            "snapshot_sha256": snapshot_hash,
            "unit_id": self.unit_id,
            "recorder_id": str(self.installer.pk),
            "reviewer_id": str(self.comptroller.pk),
            "independently_examined": True,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
        }

        self.review = ProjectEvidence.objects.create(
            msr=self.msr,
            kind=REVIEW_KIND,
            created_by=self.comptroller,
            data=review_data,
            digest=canonical_hash(review_data),
        )

        unit = ReviewedEquipmentUnit(
            unit_id=self.unit_id,
            serial_number=self.serial,
            pending_evidence_id=str(self.capture.pk),
            review_evidence_id=str(self.review.pk),
            pending_digest=self.capture.digest,
            review_digest=self.review.digest,
        )

        self.manifest = ReceiptEquipmentManifest(
            project_id=str(self.project.pk),
            msr_id=str(self.msr.pk),
            msr_version=self.msr.number,
            snapshot_sha256=snapshot_hash,
            expected_units=1,
            reviewed_units=(unit,),
            blockers=(),
            all_candidates_reviewed=True,
        )

    def patched_manifest(self, *, audit_error=None):
        stack = ExitStack()

        stack.enter_context(patch.dict(
            os.environ,
            {"GECC_EQUIPMENT_TRUST_TEST_ENABLED": "1"},
        ))

        stack.enter_context(patch(
            WRITER + ".build_receipt_equipment_manifest",
            return_value=self.manifest,
        ))

        stack.enter_context(patch(
            READER + ".build_receipt_equipment_manifest",
            return_value=self.manifest,
        ))

        auditor = stack.enter_context(patch(WRITER + ".audit"))
        if audit_error is not None:
            auditor.side_effect = audit_error

        return stack

    def decide(self, *, actor=None, approve=True):
        return record_equipment_trust_decision(
            actor=self.ceo if actor is None else actor,
            project_id=self.project.pk,
            unit_id=self.unit_id,
            approve=approve,
            decision_reason=(
                "Independent review of physical equipment "
                "and supporting evidence."
            ),
        )

    def test_real_approval_and_independent_verification(self):
        self.prepare()

        with self.patched_manifest():
            decision = self.decide()
            verified = verify_equipment_trust_decisions(self.project)

        self.assertEqual(decision.decision, "APPROVED")
        self.assertTrue(decision.trusted_equipment_decision_recorded)
        self.assertTrue(verified.all_approval_decisions_verified)
        self.assertEqual(verified.approved_decisions_verified, 1)
        self.assertFalse(verified.trusted_installation_evidence)
        self.assertFalse(verified.installation_authorized)
        self.assertFalse(verified.receipt_issuance_authorized)
        self.assertFalse(verified.customer_delivery_verified)
        self.assertFalse(verified.completion_authorized)

        stored = ProjectEvidence.objects.get(pk=decision.evidence_id)
        self.assertEqual(stored.digest, canonical_hash(stored.data))
        self.assertEqual(stored.created_by_id, self.ceo.pk)

        print("PASS: Real approved adjudication independently verified.")
        print("PASS: Approval grants no downstream authority.")

    def test_rejection_remains_a_rejection(self):
        self.prepare()

        with self.patched_manifest():
            decision = self.decide(approve=False)
            verified = verify_equipment_trust_decisions(self.project)

        self.assertEqual(decision.decision, "REJECTED")
        self.assertFalse(decision.trusted_equipment_decision_recorded)
        self.assertFalse(verified.all_approval_decisions_verified)
        self.assertEqual(verified.rejected_decisions_verified, 1)

        print("PASS: Rejected CEO decision remains blocked.")

    def test_duplicate_adjudication_rejected(self):
        self.prepare()

        with self.patched_manifest():
            self.decide()
            with self.assertRaises(ValidationError):
                self.decide()

        self.assertEqual(
            ProjectEvidence.objects.filter(msr=self.msr, kind=KIND).count(),
            1,
        )
        print("PASS: Second decision cannot replace first decision.")

    def test_role_separation_and_default_deny(self):
        self.prepare()

        with self.assertRaises(PermissionDenied):
            self.decide()

        with self.patched_manifest():
            for actor in (self.comptroller, self.installer, self.sales):
                with self.assertRaises(PermissionDenied):
                    self.decide(actor=actor)

        self.assertEqual(
            ProjectEvidence.objects.filter(msr=self.msr, kind=KIND).count(),
            0,
        )
        print("PASS: Default deny and unauthorized roles enforced.")

    def test_audit_failure_rolls_back_adjudication(self):
        self.prepare()

        with self.patched_manifest(
            audit_error=RuntimeError("FICTIONAL AUDIT FAILURE")
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "FICTIONAL AUDIT FAILURE",
            ):
                self.decide()

        self.assertFalse(
            ProjectEvidence.objects.filter(msr=self.msr, kind=KIND).exists()
        )
        print("PASS: Audit failure rolls back decision evidence.")

    def test_database_immutability_and_read_side_integrity(self):
        self.prepare()

        with self.patched_manifest():
            decision = self.decide()
            stored = ProjectEvidence.objects.get(
                pk=decision.evidence_id
            )
            original_digest = stored.digest

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    ProjectEvidence.objects.filter(
                        pk=stored.pk
                    ).update(digest="0" * 64)

            intact = ProjectEvidence.objects.get(pk=stored.pk)
            self.assertEqual(intact.digest, original_digest)

            # Simulate a corrupted read-side record without modifying
            # immutable historical data in the database.
            from copy import copy
            altered = copy(intact)
            altered.data = {
                **intact.data,
                "serial_number": "CHANGED-SERIAL",
            }

            original_filter = ProjectEvidence.objects.filter

            def filtered(*args, **kwargs):
                if kwargs.get("kind") == KIND:
                    return [altered]
                return original_filter(*args, **kwargs)

            with patch(
                READER + ".ProjectEvidence.objects.filter",
                side_effect=filtered,
            ):
                with self.assertRaises(ValueError):
                    verify_equipment_trust_decisions(self.project)

        print("PASS: Database immutable evidence trigger enforced.")
        print("PASS: Modified adjudication rejected on read.")
