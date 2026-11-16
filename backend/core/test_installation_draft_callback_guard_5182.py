from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from core import installation_draft_oauth_5181 as service
from core.installation_provider_oauth_4979 import Role, canonical_hash


class InspectionCallbackGuard5182Tests(SimpleTestCase):
    def setUp(self):
        self.reviewer = SimpleNamespace(pk=8, role=Role.COMPTROLLER)
        self.approver = SimpleNamespace(pk=7, role=Role.CEO, is_active=True)
        self.project = SimpleNamespace(
            pk="project-1", state="ACTIVE", current_approved_id="msr-1"
        )
        self.msr = SimpleNamespace(
            pk="msr-1", project_id="project-1", project=self.project,
            status="APPROVED", number=2
        )
        self.data = {
            "schema": "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1",
            "state": "DRAFT_INTENT_RECORDED",
            "project_id": "project-1",
            "msr_id": "msr-1",
            "msr_version": "2",
            "authorized_by_id": "7",
            "draft_payload_sha256": "b" * 64,
            "provider_draft_created": False,
            "provider_request_authorized": False,
            "send_authorized": False,
            "provider_signature_verified": False,
            "inspection_findings_verified": False,
            "receipt_issuance_authorized": False,
            "project_completion_authorized": False,
        }
        self.intent = SimpleNamespace(
            pk="intent-1", data=self.data, created_by_id=7,
            msr=self.msr, digest=canonical_hash(self.data)
        )
        self.challenge = SimpleNamespace(
            actor_id=8,
            context={
                "operation": service.OPERATION,
                "intent_id": "intent-1",
                "intent_digest": self.intent.digest,
                "project_id": "project-1",
                "draft_payload_sha256": "b" * 64,
                "provider_request_authorized": False,
                "send_authorized": False,
            },
        )

        self.gate = patch.object(
            service, "_gate", return_value=self.reviewer
        ).start()
        self.addCleanup(patch.stopall)

        self.proof = patch.object(
            service.ProjectEvidence.objects, "filter"
        ).start()
        self.proof.return_value.first.return_value = self.intent

        self.users = patch.object(
            service.User.objects, "filter"
        ).start()
        self.users.return_value.first.return_value = self.approver

        self.config = patch.object(
            service.docusign, "configuration",
            return_value={"account_id": "sandbox", "blockers": []}
        ).start()
        self.audit = patch.object(service, "audit").start()

    def callback(self):
        return service.finish(
            self.reviewer,
            self.challenge,
            {"account_id": "sandbox", "blockers": []},
            "transient-test-token",
        )

    def test_valid_context_still_grants_no_provider_authority(self):
        result = self.callback()
        self.assertEqual(result["status"], "SANDBOX_IM_DRAFT_CONTEXT_CHECKED")
        self.assertFalse(result["provider_request_authorized"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["project_completion_authorized"])
        self.audit.assert_called_once()

    def test_cancelled_project_rejected(self):
        self.project.state = "CANCELLED"
        with self.assertRaises(PermissionDenied):
            self.callback()
        self.audit.assert_not_called()

    def test_superseded_msr_rejected(self):
        self.project.current_approved_id = "new-msr"
        with self.assertRaises(PermissionDenied):
            self.callback()
        self.audit.assert_not_called()

    def test_revoked_authorizer_rejected(self):
        self.approver.is_active = False
        self.users.return_value.first.return_value = None
        with self.assertRaises(PermissionDenied):
            self.callback()
        self.audit.assert_not_called()

    def test_authorizer_role_changed_rejected(self):
        self.approver.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.callback()
        self.audit.assert_not_called()

    def test_elevated_authority_rejected(self):
        self.data["send_authorized"] = True
        self.intent.digest = canonical_hash(self.data)
        self.challenge.context["intent_digest"] = self.intent.digest
        with self.assertRaises(PermissionDenied):
            self.callback()
        self.audit.assert_not_called()

    def test_msr_version_changed_rejected(self):
        self.msr.number = 3
        with self.assertRaises(PermissionDenied):
            self.callback()
        self.audit.assert_not_called()