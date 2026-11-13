"""Full real-service equipment chain, disposable SQLite only.

No mocked equipment manifest, capture, review, or decision verifier.
CEO adjudication remains provisional and development-only.
"""

import os
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_installation_combined_real_evidence as foundation
from .equipment_physical_capture_pending_service import (
    record_pending_physical_inspection,
)
from .equipment_physical_inspection_review_service import (
    review_pending_physical_inspection,
)
from .equipment_physical_inspection_verifier import (
    verify_physical_inspection_candidate,
)
from .equipment_physical_units import physical_units_from_snapshot
from .receipt_equipment_manifest_4768 import (
    build_receipt_equipment_manifest,
)
from .equipment_trust_decision_4784 import (
    KIND,
    record_equipment_trust_decision,
)
from .equipment_trust_verifier_4785 import (
    verify_equipment_trust_decisions,
)
from .models import AuditEvent, ProjectEvidence, Role, User


WRITER = "core.equipment_trust_decision_4784"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class FullEquipmentEvidenceChain4788(TestCase):
    def setUp(self):
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise RuntimeError("SAFETY STOP: SQLite tests only.")

        fixture = foundation.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()

        self.fixture = fixture
        self.msr = fixture.prepare()
        self.project = fixture.project

        self.units = physical_units_from_snapshot(
            msr_id=str(self.msr.pk),
            snapshot=self.msr.snapshot,
        )
        self.assertTrue(self.units)

        self.comptroller = User.objects.filter(
            role=Role.COMPTROLLER,
            is_active=True,
        ).first()
        self.assertIsNotNone(self.comptroller)

        self.ceo = User.objects.create_user(
            username="full-chain-ceo-4788",
            password=None,
            role=Role.CEO,
            initials="FC",
        )

    def prepare_real_evidence(self, *, reject_unit=None):
        now = timezone.now()

        for index, unit in enumerate(self.units, start=1):
            pending = record_pending_physical_inspection(
                actor=self.fixture.installation_manager,
                project_id=self.project.pk,
                msr_id=str(self.msr.pk),
                unit_id=unit.unit_id,
                serial_number=f"GOODMAN-FULL-4788-{index:03d}",
                captured_at=now,
                installation_starts_at=now + timedelta(hours=1),
                confirmed_in_person=True,
                inspection_notes=(
                    "Physical serial-number label personally inspected "
                    "and recorded against this approved unit."
                ),
            )

            self.assertFalse(
                pending.data["trusted_installation_evidence"]
            )

            accepted = unit.unit_id != reject_unit

            review = review_pending_physical_inspection(
                actor=self.comptroller,
                pending_id=pending.pk,
                accept_candidate=accepted,
                review_reason=(
                    "Independent physical-unit evidence reviewed "
                    "against the approved customer project."
                ),
                independently_examined=accepted,
            )

            self.assertFalse(
                review.data["trusted_installation_evidence"]
            )

        return build_receipt_equipment_manifest(self.project)

    def decide(self, unit_id, *, actor=None, approve=True):
        with patch.dict(
            os.environ,
            {"GECC_EQUIPMENT_TRUST_TEST_ENABLED": "1"},
        ):
            return record_equipment_trust_decision(
                actor=self.ceo if actor is None else actor,
                project_id=self.project.pk,
                unit_id=unit_id,
                approve=approve,
                decision_reason=(
                    "Separate independent adjudication of reviewed "
                    "physical equipment identity and provenance."
                ),
            )

    def assert_no_downstream_authority(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

    def test_complete_real_capture_review_decision_chain(self):
        manifest = self.prepare_real_evidence()

        self.assertTrue(manifest.all_candidates_reviewed)
        self.assertEqual(
            len(manifest.reviewed_units),
            len(self.units),
        )

        before = verify_equipment_trust_decisions(self.project)
        self.assertFalse(before.all_approval_decisions_verified)
        self.assert_no_downstream_authority(before)

        for unit in manifest.reviewed_units:
            independently_checked = verify_physical_inspection_candidate(
                project_id=str(self.project.pk),
                msr_id=str(self.msr.pk),
                unit_id=unit.unit_id,
            )
            self.assertTrue(
                independently_checked.review_candidate_verified
            )
            self.assertFalse(
                independently_checked.trusted_installation_evidence
            )

            decision = self.decide(unit.unit_id)
            self.assertEqual(decision.decision, "APPROVED")
            self.assertFalse(decision.installation_authorized)
            self.assertFalse(decision.receipt_issuance_authorized)

        verified = verify_equipment_trust_decisions(self.project)

        self.assertTrue(verified.all_approval_decisions_verified)
        self.assertEqual(
            verified.approved_decisions_verified,
            len(self.units),
        )
        self.assert_no_downstream_authority(verified)

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).count(),
            len(self.units),
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.trust_decision_recorded"
            ).count(),
            len(self.units),
        )

        print(
            "PASS: Real capture, review, manifest, CEO decision, "
            "and independent verification."
        )
        print("PASS: All adjudications audited and downstream blocked.")

    def test_missing_review_prevents_trust_decision(self):
        manifest = self.prepare_real_evidence(
            reject_unit=self.units[0].unit_id
        )

        self.assertFalse(manifest.all_candidates_reviewed)

        with self.assertRaises(ValidationError):
            self.decide(self.units[0].unit_id)

        with self.assertRaises(ValueError):
            verify_equipment_trust_decisions(self.project)

        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).exists()
        )

        print("PASS: Rejected physical review blocks adjudication.")

    def test_rejected_ceo_decision_does_not_grant_trust(self):
        manifest = self.prepare_real_evidence()
        self.assertTrue(manifest.all_candidates_reviewed)

        rejected_unit = manifest.reviewed_units[0].unit_id

        for unit in manifest.reviewed_units:
            self.decide(
                unit.unit_id,
                approve=(unit.unit_id != rejected_unit),
            )

        result = verify_equipment_trust_decisions(self.project)
        self.assertFalse(result.all_approval_decisions_verified)
        self.assertEqual(result.rejected_decisions_verified, 1)
        self.assert_no_downstream_authority(result)

        print("PASS: Rejected CEO decision remains durable and blocked.")

    def test_duplicate_and_unauthorized_decisions_denied(self):
        manifest = self.prepare_real_evidence()
        unit_id = manifest.reviewed_units[0].unit_id

        with self.assertRaises(PermissionDenied):
            self.decide(
                unit_id, actor=self.fixture.installation_manager
            )

        with self.assertRaises(PermissionDenied):
            self.decide(unit_id, actor=self.comptroller)

        first = self.decide(unit_id)

        with self.assertRaises(ValidationError):
            self.decide(unit_id)

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr,
                kind=KIND,
                pk=first.evidence_id,
            ).count(),
            1,
        )

        print("PASS: Separation of duties and duplicate denial.")

    def test_audit_failure_rolls_back_real_chain_decision(self):
        manifest = self.prepare_real_evidence()
        unit_id = manifest.reviewed_units[0].unit_id

        with patch(
            WRITER + ".audit",
            side_effect=RuntimeError("FICTIONAL AUDIT FAILURE"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "FICTIONAL AUDIT FAILURE"
            ):
                self.decide(unit_id)

        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).exists()
        )

        print("PASS: Audit failure rolls back real-chain adjudication.")
