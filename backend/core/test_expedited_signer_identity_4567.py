from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import CustomerSignerAuthorization
from .expedited_signer_identity_4567 import (
    assess_expedited_customer_identity,
)

MODULE = "core.expedited_signer_identity_4567"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedSignerIdentity4567Tests(SimpleTestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.msr_id = uuid4()
        self.customer_id = uuid4()
        self.approval_id = uuid4()
        self.actor = SimpleNamespace(pk=uuid4())
        self.preflight = {
            "project_id": str(self.project_id),
            "msr_id": str(self.msr_id),
            "msr_version": 3,
            "snapshot_sha256": "a" * 64,
            "proposed_date": "2026-11-15",
            "administrative_chain_reviewed": True,
            "send_authorized": False,
            "installation_authorized": False,
        }
        self.project = SimpleNamespace(
            pk=self.project_id,
            state="ACTIVE",
            current_approved_id=self.msr_id,
            current_approved=SimpleNamespace(
                pk=self.msr_id, status="APPROVED", number=3
            ),
            customer_id=self.customer_id,
            customer=SimpleNamespace(archived=False),
        )
        self.approval = SimpleNamespace(
            pk=self.approval_id,
            project_id=self.project_id,
            approved_msr_id=self.msr_id,
            customer_id=self.customer_id,
            group=CustomerSignerAuthorization.Group.COMMERCIAL,
            signer_name="Fictional Customer",
            signer_email="fictional@example.invalid",
            digest="b" * 64,
        )
        self.approvals = [self.approval]
        self.audit_ok = True

    def check(self):
        with (
            patch(
                f"{MODULE}.assess_unified_signing_preflight",
                return_value=self.preflight,
            ),
            patch(f"{MODULE}.Project.objects.select_related") as projects,
            patch(
                f"{MODULE}.CustomerSignerAuthorization.objects.filter"
            ) as approvals,
            patch(
                f"{MODULE}.verify_customer_signer_integrity"
            ) as integrity,
        ):
            projects.return_value.filter.return_value.first.return_value = (
                self.project
            )
            approvals.return_value.__getitem__.return_value = (
                self.approvals
            )
            integrity.return_value = (
                self.approval if self.audit_ok else None
            )
            return assess_expedited_customer_identity(
                actor=self.actor,
                project_id=str(self.project_id),
            )

    def test_valid_identity_remains_without_expedited_authority(self):
        result = self.check()
        self.assertEqual(result["msr_id"], str(self.msr_id))
        self.assertEqual(
            result["commercial_signer_authorization_id"],
            str(self.approval_id),
        )
        self.assertFalse(result["expedited_signer_authorized"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["installation_authorized"])

    def test_missing_approval_rejected(self):
        self.approvals = []
        with self.assertRaises(ValidationError):
            self.check()

    def test_ambiguous_approvals_rejected(self):
        self.approvals = [self.approval, self.approval]
        with self.assertRaises(ValidationError):
            self.check()

    def test_wrong_approved_msr_rejected(self):
        self.approval.approved_msr_id = uuid4()
        with self.assertRaises(ValidationError):
            self.check()

    def test_wrong_customer_rejected(self):
        self.approval.customer_id = uuid4()
        with self.assertRaises(ValidationError):
            self.check()

    def test_wrong_signer_group_rejected(self):
        self.approval.group = "COMPLETION_FINANCED"
        with self.assertRaises(ValidationError):
            self.check()

    def test_missing_audit_proof_rejected(self):
        self.audit_ok = False
        with self.assertRaises(ValidationError):
            self.check()

    def test_archived_customer_rejected(self):
        self.project.customer.archived = True
        with self.assertRaises(ValidationError):
            self.check()

    def test_superseded_msr_rejected(self):
        self.project.current_approved_id = uuid4()
        with self.assertRaises(ValidationError):
            self.check()

    def test_preflight_permission_failure_propagates(self):
        with patch(
            f"{MODULE}.assess_unified_signing_preflight",
            side_effect=PermissionDenied("Denied"),
        ):
            with self.assertRaises(PermissionDenied):
                assess_expedited_customer_identity(
                    actor=self.actor,
                    project_id=str(self.project_id),
                )

    def test_preflight_authority_flag_rejected(self):
        self.preflight["send_authorized"] = True
        with self.assertRaises(ValidationError):
            self.check()

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            assess_expedited_customer_identity(
                actor=self.actor,
                project_id=str(self.project_id),
            )
