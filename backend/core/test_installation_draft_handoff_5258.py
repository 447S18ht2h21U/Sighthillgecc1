"""Protected inspection draft handoff boundary tests."""
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core.models import Role
from core.installation_provider_oauth_4979 import canonical_hash
from core import installation_draft_handoff_5258 as service

P = "project-5258"
M = "msr-5258"
H = "a" * 64


@override_settings(ENVIRONMENT="development", DEBUG=True)
class InspectionDraftHandoff5258Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk="user-1", is_active=True, role=Role.CEO
        )
        self.msr = SimpleNamespace(
            pk=M, project_id=P, number=5, status="APPROVED"
        )
        self.project = SimpleNamespace(
            pk=P, state="ACTIVE",
            current_approved=self.msr,
            current_approved_id=M,
        )
        self.data = {
            "schema": "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1",
            "state": "DRAFT_INTENT_RECORDED",
            "project_id": P, "msr_id": M,
            "msr_version": "5",
            "authorized_by_id": "user-2",
            "draft_payload_sha256": H,
            "provider_draft_created": False,
            "provider_request_authorized": False,
            "send_authorized": False,
            "provider_signature_verified": False,
            "inspection_findings_verified": False,
            "receipt_issuance_authorized": False,
            "project_completion_authorized": False,
        }
        self.record = SimpleNamespace(
            pk="intent-1", msr_id=M,
            created_by_id="user-2", data=self.data,
            digest=canonical_hash(self.data),
        )
        self.envelope = SimpleNamespace(
            project_id=P,
            approved_msr_id=M,
            approved_msr_version="5",
            envelope_id=None,
            state="LOCAL_DRAFT_NOT_SUBMITTED",
            provider_signed=False,
            completion_authorized=False,
        )

    def check(self, records=None):
        if records is None:
            records = [self.record]
        with (
            patch.object(service, "_isolated_gate"),
            patch.object(
                service.Project.objects, "select_related"
            ) as projects,
            patch.object(
                service.ProjectEvidence.objects, "filter",
                return_value=records,
            ),
            patch.object(service.User.objects, "filter") as users,
            patch.object(
                service, "assemble", return_value=self.envelope
            ) as assemble,
            patch.object(
                service, "_fingerprint", return_value=H
            ),
        ):
            projects.return_value.filter.return_value.first.return_value = (
                self.project
            )
            users.return_value.first.return_value = SimpleNamespace(
                role=Role.CEO
            )
            result = service.verify_handoff(
                actor=self.actor, project_id=P
            )
        return result, assemble

    def test_matching_handoff_remains_read_only(self):
        result, builder = self.check()
        builder.assert_called_once()
        self.assertEqual(result["state"], "OFFLINE_DRAFT_HANDOFF_MATCHED")
        self.assertTrue(result["read_only"])
        for name in (
            "provider_request_authorized",
            "provider_envelope_created",
            "send_authorized",
            "provider_signature_verified",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertIs(result[name], False)

    def test_missing_intent_rejected(self):
        with self.assertRaises(ValidationError):
            self.check(records=[])

    def test_duplicate_intent_rejected(self):
        with self.assertRaises(ValidationError):
            self.check(records=[self.record, self.record])

    def test_changed_msr_rejected(self):
        self.msr.number = 6
        with self.assertRaises(ValidationError):
            self.check()

    def test_tampered_authorization_rejected(self):
        self.data["send_authorized"] = True
        self.record.digest = canonical_hash(self.data)
        with self.assertRaises(ValidationError):
            self.check()

    def test_wrong_project_rejected(self):
        self.envelope.project_id = "another-project"
        with self.assertRaises(ValidationError):
            self.check()

    def test_gate_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionDenied):
                service._isolated_gate(self.actor)

    def test_gate_rejects_persistent_database(self):
        fake = SimpleNamespace(
            vendor="sqlite",
            settings_dict={"NAME": "development.sqlite3"},
        )
        with (
            patch.dict(
                os.environ,
                {"GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1"}
            ),
            patch.object(service, "connection", fake),
        ):
            with self.assertRaises(PermissionDenied):
                service._isolated_gate(self.actor)

    def test_gate_rejects_comptroller(self):
        self.actor.role = Role.COMPTROLLER
        fake = SimpleNamespace(
            vendor="sqlite",
            settings_dict={"NAME": ":memory:"},
        )
        with (
            patch.dict(
                os.environ,
                {"GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1"}
            ),
            patch.object(service, "connection", fake),
        ):
            with self.assertRaises(PermissionDenied):
                service._isolated_gate(self.actor)
