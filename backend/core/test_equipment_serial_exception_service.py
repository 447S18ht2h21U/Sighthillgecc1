"""Isolated database security tests for serial exception requests."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_serial_exception_service import (
    REQUEST_KIND,
    request_serial_exception,
)
from .models import AuditEvent, ProjectEvidence, Role, User
from .tests import FoundationTests


@override_settings(DEBUG=True, ENVIRONMENT="development")
class SerialExceptionRequestServiceTests(TestCase):
    edit_submit = FoundationTests.edit_submit
    approve = FoundationTests.approve

    def setUp(self):
        FoundationTests.setUp(self)
        self.installation_manager = User.objects.create_user(
            username="serial_exception_test_installation_manager",
            password="synthetic-test-only",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )

    def prepare(self):
        self.snapshot["equipment"] = [{
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Synthetic equipment for exception tests",
            "quantity": 2,
            "category_of_work": "New installation",
        }]
        approved = self.approve()
        self.project.refresh_from_db()
        return approved

    def request(self, msr, **changes):
        arguments = {
            "actor": self.installation_manager,
            "project_id": self.project.pk,
            "msr_id": msr.pk,
            "unit_id": "ROW-001-UNIT-001",
            "reason": "The manufacturer confirms that a serial is not applicable.",
        }
        arguments.update(changes)
        return request_serial_exception(**arguments)

    def test_request_is_immutable_unapproved_and_audited(self):
        msr = self.prepare()
        evidence = self.request(msr)
        self.assertEqual(evidence.kind, REQUEST_KIND)
        self.assertEqual(evidence.data["status"], "REQUESTED")
        self.assertFalse(evidence.data["exception_effective"])
        self.assertFalse(evidence.data["installation_authorized"])
        self.assertEqual(
            evidence.digest, canonical_hash(evidence.data)
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.serial_exception_requested"
            ).count(), 1
        )
        self.assertEqual(evidence.msr_id, msr.pk)

    def test_wrong_role_is_denied(self):
        msr = self.prepare()
        with self.assertRaises(PermissionDenied):
            self.request(msr, actor=self.sales)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REQUEST_KIND).exists()
        )

    def test_wrong_unit_is_rejected(self):
        msr = self.prepare()
        with self.assertRaises(ValidationError):
            self.request(msr, unit_id="ROW-004-UNIT-001")
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REQUEST_KIND).exists()
        )

    def test_duplicate_request_is_denied(self):
        msr = self.prepare()
        self.request(msr)
        with self.assertRaises(ValidationError):
            self.request(msr)
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=REQUEST_KIND).count(), 1
        )

    def test_audit_failure_rolls_back_evidence(self):
        msr = self.prepare()
        with patch(
            "core.equipment_serial_exception_service.audit",
            side_effect=RuntimeError("synthetic audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic audit failure"
            ):
                self.request(msr)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REQUEST_KIND).exists()
        )

    def decide(self, request, **changes):
        from .equipment_serial_exception_service import decide_serial_exception
        values = {
            "actor": self.comptroller,
            "request_id": request.pk,
            "approve": True,
            "decision_reason": "Verified the manufacturer's written non-applicability statement.",
            "genuinely_not_applicable": True,
        }
        values.update(changes)
        return decide_serial_exception(**values)

    def test_comptroller_decision_is_audited(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        self.assertEqual(decision.data["status"], "APPROVED")
        self.assertEqual(decision.data["request_id"], str(request.pk))
        self.assertFalse(decision.data["exception_effective"])
        self.assertFalse(decision.data["installation_authorized"])
        self.assertEqual(decision.digest, canonical_hash(decision.data))
        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.serial_exception_decided"
            ).count(), 1
        )

    def test_rejection_remains_immutable_and_ineffective(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(
            request, approve=False, genuinely_not_applicable=False
        )
        self.assertEqual(decision.data["status"], "REJECTED")
        self.assertFalse(decision.data["comptroller_approved"])
        self.assertFalse(decision.data["exception_effective"])

    def test_non_comptroller_cannot_decide(self):
        msr = self.prepare()
        request = self.request(msr)
        with self.assertRaises(PermissionDenied):
            self.decide(request, actor=self.installation_manager)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_duplicate_decision_is_denied(self):
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        with self.assertRaises(ValidationError):
            self.decide(request)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).count(), 1
        )

    def test_approval_requires_explicit_non_applicability(self):
        msr = self.prepare()
        request = self.request(msr)
        with self.assertRaises(ValidationError):
            self.decide(request, genuinely_not_applicable=False)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_decision_audit_failure_rolls_back(self):
        msr = self.prepare()
        request = self.request(msr)
        with patch(
            "core.equipment_serial_exception_service.audit",
            side_effect=RuntimeError("synthetic decision audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic decision audit failure"
            ):
                self.decide(request)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_inactive_comptroller_cannot_decide(self):
        msr = self.prepare()
        request = self.request(msr)
        User.objects.filter(pk=self.comptroller.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.decide(request)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_production_environment_cannot_record_decision(self):
        msr = self.prepare()
        request = self.request(msr)
        with override_settings(ENVIRONMENT="production", DEBUG=False):
            with self.assertRaises(ValidationError):
                self.decide(request)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_decision_must_be_explicit_boolean(self):
        msr = self.prepare()
        request = self.request(msr)
        for value in (None, 1, "true", "approve"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.decide(request, approve=value)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_decision_requires_written_reason(self):
        msr = self.prepare()
        request = self.request(msr)
        for value in ("", " ", "Approved"):
            with self.subTest(reason=value):
                with self.assertRaises(ValidationError):
                    self.decide(request, decision_reason=value)
        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_wrong_evidence_kind_cannot_be_decided(self):
        from .equipment_serial_exception_service import DECISION_KIND
        msr = self.prepare()
        payload = {"purpose": "Synthetic unrelated evidence regression"}
        unrelated = ProjectEvidence.objects.create(
            msr=msr,
            kind="UNRELATED_TEST_EVIDENCE",
            created_by=self.installation_manager,
            data=payload,
            digest=canonical_hash(payload),
        )
        with self.assertRaises(ValidationError):
            self.decide(unrelated)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )
        self.assertEqual(
            ProjectEvidence.objects.get(pk=unrelated.pk).kind,
            "UNRELATED_TEST_EVIDENCE",
        )

    def test_two_physical_units_require_separate_decisions(self):
        from .equipment_serial_exception_service import DECISION_KIND
        msr = self.prepare()
        first = self.request(msr, unit_id="ROW-001-UNIT-001")
        second = self.request(msr, unit_id="ROW-001-UNIT-002")
        first_decision = self.decide(first)
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).count(), 1
        )
        self.assertEqual(
            first_decision.data["unit_id"], "ROW-001-UNIT-001"
        )
        self.assertNotEqual(
            first_decision.data["request_id"], str(second.pk)
        )
        second_decision = self.decide(
            second, approve=False, genuinely_not_applicable=False
        )
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).count(), 2
        )
        self.assertEqual(
            second_decision.data["unit_id"], "ROW-001-UNIT-002"
        )
        self.assertFalse(second_decision.data["exception_effective"])
        self.assertFalse(first_decision.data["installation_authorized"])

    def revoke(self, decision, **changes):
        from .equipment_serial_exception_service import revoke_serial_exception
        values = {
            "actor": self.comptroller,
            "decision_id": decision.pk,
            "reason": "Verified replacement paperwork now requires a serial.",
        }
        values.update(changes)
        return revoke_serial_exception(**values)

    def test_serial_revocation_is_immutable(self):
        from .equipment_serial_exception_service import REVOCATION_KIND
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        previous_digest = decision.digest
        revocation = self.revoke(decision)
        self.assertEqual(revocation.kind, REVOCATION_KIND)
        self.assertEqual(revocation.data["status"], "REVOKED")
        self.assertFalse(revocation.data["exception_effective"])
        self.assertFalse(revocation.data["installation_authorized"])
        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.serial_exception_revoked"
            ).count(), 1
        )
        decision.refresh_from_db()
        self.assertEqual(decision.digest, previous_digest)
        self.assertEqual(decision.data["status"], "APPROVED")

    def test_non_comptroller_cannot_revoke(self):
        from .equipment_serial_exception_service import REVOCATION_KIND
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        with self.assertRaises(PermissionDenied):
            self.revoke(decision, actor=self.installation_manager)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REVOCATION_KIND).exists()
        )

    def test_duplicate_revocation_is_rejected(self):
        from .equipment_serial_exception_service import REVOCATION_KIND
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        self.revoke(decision)
        with self.assertRaises(ValidationError):
            self.revoke(decision)
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=REVOCATION_KIND).count(), 1
        )

    def test_rejected_decision_cannot_be_revoked_as_approval(self):
        from .equipment_serial_exception_service import REVOCATION_KIND
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(
            request, approve=False, genuinely_not_applicable=False
        )
        with self.assertRaises(ValidationError):
            self.revoke(decision)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REVOCATION_KIND).exists()
        )

    def test_revocation_audit_failure_rolls_back(self):
        from .equipment_serial_exception_service import REVOCATION_KIND
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        with patch(
            "core.equipment_serial_exception_service.audit",
            side_effect=RuntimeError("synthetic revocation audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic revocation audit failure"
            ):
                self.revoke(decision)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REVOCATION_KIND).exists()
        )

    def verify_candidate(self, msr, unit_id="ROW-001-UNIT-001"):
        from .equipment_serial_exception_verifier import (
            verify_serial_exception_candidate,
        )
        return verify_serial_exception_candidate(
            project_id=self.project.pk,
            msr_id=msr.pk,
            unit_id=unit_id,
        )

    def test_readonly_verifier_recognizes_approved_candidate(self):
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        audit_count = AuditEvent.objects.count()
        evidence_count = ProjectEvidence.objects.count()
        result = self.verify_candidate(msr)
        self.assertTrue(result.approval_candidate_verified)
        self.assertFalse(result.exception_effective)
        self.assertFalse(result.installation_authorized)
        self.assertEqual(AuditEvent.objects.count(), audit_count)
        self.assertEqual(ProjectEvidence.objects.count(), evidence_count)

    def test_readonly_verifier_requires_decision(self):
        msr = self.prepare()
        self.request(msr)
        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )

    def test_readonly_verifier_rejects_negative_decision(self):
        msr = self.prepare()
        request = self.request(msr)
        self.decide(
            request, approve=False, genuinely_not_applicable=False
        )
        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )

    def test_readonly_verifier_rejects_revoked_decision(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        self.revoke(decision)
        result = self.verify_candidate(msr)
        self.assertFalse(result.approval_candidate_verified)
        self.assertFalse(result.installation_authorized)

    def test_readonly_verifier_is_unit_specific(self):
        msr = self.prepare()
        request = self.request(msr, unit_id="ROW-001-UNIT-001")
        self.decide(request)
        self.assertTrue(
            self.verify_candidate(msr, "ROW-001-UNIT-001").approval_candidate_verified
        )
        self.assertFalse(
            self.verify_candidate(msr, "ROW-001-UNIT-002").approval_candidate_verified
        )

    def test_readonly_verifier_rejects_wrong_msr(self):
        from .equipment_serial_exception_verifier import (
            verify_serial_exception_candidate,
        )
        from uuid import uuid4
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        result = verify_serial_exception_candidate(
            project_id=self.project.pk,
            msr_id=uuid4(),
            unit_id="ROW-001-UNIT-001",
        )
        self.assertFalse(result.approval_candidate_verified)

    def test_verifier_rejects_cancelled_project(self):
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        self.project.state = "CANCELLED"
        self.project.save(update_fields=["state"])
        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )

    def test_verifier_rejects_missing_current_approval(self):
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        self.project.current_approved = None
        self.project.save(update_fields=["current_approved"])
        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )

    def test_verifier_rejects_duplicate_request_evidence(self):
        from .equipment_serial_exception_service import REQUEST_KIND
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        clone = ProjectEvidence.objects.create(
            msr=msr,
            kind=REQUEST_KIND,
            created_by=request.created_by,
            data=dict(request.data),
            digest=request.digest,
        )
        self.assertNotEqual(request.pk, clone.pk)
        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )

    def test_verifier_rejects_duplicate_decision_evidence(self):
        from .equipment_serial_exception_service import DECISION_KIND
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        clone = ProjectEvidence.objects.create(
            msr=msr,
            kind=DECISION_KIND,
            created_by=decision.created_by,
            data=dict(decision.data),
            digest=decision.digest,
        )
        self.assertNotEqual(decision.pk, clone.pk)
        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )

    def test_verifier_rejects_extra_unit_revocation(self):
        from .equipment_serial_exception_service import REVOCATION_KIND
        msr = self.prepare()
        request = self.request(msr)
        self.decide(request)
        payload = {
            "unit_id": "ROW-001-UNIT-001",
            "decision_id": "unrelated-synthetic-reference",
            "status": "REVOKED",
        }
        ProjectEvidence.objects.create(
            msr=msr,
            kind=REVOCATION_KIND,
            created_by=self.comptroller,
            data=payload,
            digest=canonical_hash(payload),
        )
        result = self.verify_candidate(msr)
        self.assertFalse(result.approval_candidate_verified)
        self.assertFalse(result.exception_effective)
        self.assertFalse(result.installation_authorized)

    def make_synthetic_approved_revision(self, original):
        """Test-only replacement of the current approved MSR pointer."""
        from copy import deepcopy
        from .models import MSR

        revised = MSR.objects.create(
            project=self.project,
            number=original.number + 1,
            status="APPROVED",
            snapshot=deepcopy(original.snapshot),
            created_by=original.created_by,
            prepared_by=original.prepared_by,
            approved_by=original.approved_by,
            source=original,
            revision_reason="Synthetic security regression only",
        )
        self.project.current_approved = revised
        self.project.save(update_fields=["current_approved"])
        self.project.refresh_from_db()
        return revised

    def test_revision_excludes_previous_msr_exception(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        self.assertTrue(
            self.verify_candidate(msr).approval_candidate_verified
        )

        revised = self.make_synthetic_approved_revision(msr)
        self.assertEqual(revised.snapshot["equipment"], msr.snapshot["equipment"])
        self.assertNotEqual(revised.pk, msr.pk)

        self.assertFalse(
            self.verify_candidate(msr).approval_candidate_verified
        )
        self.assertFalse(
            self.verify_candidate(revised).approval_candidate_verified
        )
        decision.refresh_from_db()
        self.assertEqual(decision.data["msr_id"], str(msr.pk))
        self.assertEqual(decision.data["status"], "APPROVED")

    def test_revision_blocks_new_decision_on_old_request(self):
        msr = self.prepare()
        request = self.request(msr)
        self.make_synthetic_approved_revision(msr)
        with self.assertRaises(ValidationError):
            self.decide(request)

        from .equipment_serial_exception_service import DECISION_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )

    def test_revision_blocks_new_request_for_previous_msr(self):
        msr = self.prepare()
        self.make_synthetic_approved_revision(msr)
        with self.assertRaises(ValidationError):
            self.request(msr)

        from .equipment_serial_exception_service import REQUEST_KIND
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=REQUEST_KIND).exists()
        )