from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings

from core import installation_draft_status_5186 as service
from core.installation_provider_oauth_4979 import Role, canonical_hash


@override_settings(ENVIRONMENT="development", DEBUG=True)
class InstallationDraftStatus5186Tests(SimpleTestCase):

    def setUp(self):
        self.actor = SimpleNamespace(
            pk=7, is_active=True, role=Role.COMPTROLLER
        )
        self.msr = SimpleNamespace(
            pk="msr-1", number=2, status="APPROVED",
            project_id="project-1"
        )
        self.project = SimpleNamespace(
            pk="project-1",
            state="ACTIVE",
            current_approved=self.msr
        )
        self.data = {
            "schema": "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1",
            "state": "DRAFT_INTENT_RECORDED",
            "project_id": "project-1",
            "msr_id": "msr-1",
            "msr_version": "2",
            "authorized_by_id": "8",
            "draft_payload_sha256": "a" * 64,
        }
        for key in service.FALSE_FLAGS:
            self.data[key] = False

        self.intent = SimpleNamespace(
            pk="intent-1",
            created_by_id=8,
            data=self.data,
            digest=canonical_hash(self.data),
        )

        self.viewer_patch = patch.object(
            service, "_viewer", return_value=self.actor
        )
        self.viewer_patch.start()
        self.addCleanup(self.viewer_patch.stop)

        self.projects_patch = patch.object(
            service.Project.objects, "filter"
        )
        projects = self.projects_patch.start()
        self.addCleanup(self.projects_patch.stop)
        projects.return_value.first.return_value = self.project

        self.evidence_patch = patch.object(
            service.ProjectEvidence.objects, "filter"
        )
        self.records = self.evidence_patch.start().return_value
        self.addCleanup(self.evidence_patch.stop)
        self.records.count.return_value = 1
        self.records.first.return_value = self.intent

        self.user_patch = patch.object(
            service.User.objects, "filter"
        )
        self.users = self.user_patch.start()
        self.addCleanup(self.user_patch.stop)
        self.users.return_value.first.return_value = SimpleNamespace(
            role=Role.CEO
        )

        self.readiness_patch = patch.object(
            service, "_readiness", return_value=False
        )
        self.readiness_patch.start()
        self.addCleanup(self.readiness_patch.stop)

        # These legacy unit tests use simplified project objects.
        # Source integrity is covered by real database-backed tests.
        self.source_patch = patch.object(
            service,
            "verify_retained_installation_source",
            return_value=False,
        )
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)

    def read(self):
        return service.status(
            actor=self.actor,
            project_id="project-1",
        )

    def test_authorized_intent_is_read_only(self):
        result = self.read()
        self.assertEqual(
            result["authorization_state"],
            "DRAFT_INTENT_RECORDED",
        )
        self.assertEqual(result["intent_id"], "intent-1")
        self.assertFalse(result["provider_request_authorized"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["project_completion_authorized"])

    def test_ready_source_is_visible_without_granting_authority(self):
        self.records.count.return_value = 0
        self.readiness_patch.stop()
        with patch.object(service, "_readiness", return_value=True):
            result = self.read()

        self.assertTrue(result["preparation_ready"])
        self.assertEqual(
            result["preparation_state"],
            "VERIFIED_FOR_OFFLINE_PREPARATION",
        )
        self.assertEqual(
            result["authorization_state"],
            "NOT_AUTHORIZED",
        )
        self.assertFalse(result["send_authorized"])

    def test_no_intent_returns_not_authorized(self):
        self.records.count.return_value = 0
        result = self.read()
        self.assertEqual(
            result["authorization_state"], "NOT_AUTHORIZED"
        )
        self.assertIsNone(result["intent_id"])

    def test_duplicate_intents_fail_closed(self):
        self.records.count.return_value = 2
        result = self.read()
        self.assertEqual(
            result["authorization_state"],
            "AUTHORIZATION_CONFLICT",
        )

    def test_changed_digest_fails_closed(self):
        self.intent.digest = "f" * 64
        result = self.read()
        self.assertEqual(
            result["authorization_state"],
            "AUTHORIZATION_INVALID",
        )

    def test_unapproved_msr_is_blocked(self):
        self.msr.status = "DRAFT"
        result = self.read()
        self.assertEqual(
            result["authorization_state"],
            "APPROVED_MSR_REQUIRED",
        )

    def test_cancelled_project_is_blocked(self):
        self.project.state = "CANCELLED"
        result = self.read()
        self.assertEqual(
            result["authorization_state"], "PROJECT_CANCELLED"
        )

    def test_changed_authorizer_role_fails_closed(self):
        self.users.return_value.first.return_value.role = Role.COMPTROLLER
        result = self.read()
        self.assertEqual(
            result["authorization_state"],
            "AUTHORIZER_INELIGIBLE",
        )

    def test_attempted_send_authority_fails_closed(self):
        self.data["send_authorized"] = True
        self.intent.digest = canonical_hash(self.data)
        result = self.read()
        self.assertEqual(
            result["authorization_state"],
            "AUTHORIZATION_INVALID",
        )

    def test_role_gate_rejects_installation_manager(self):
        # Exercise the real gate, not the status-test mock.
        self.viewer_patch.stop()
        self.actor.role = Role.INSTALLATION_MANAGER
        with self.assertRaises(PermissionDenied):
            service._viewer(self.actor)
