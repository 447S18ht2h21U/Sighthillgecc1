from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from core import installation_draft_authorization_5179 as service


class InspectionDraftIntegrity5180Tests(TestCase):
    def setUp(self):
        self.project_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        self.msr_id = "11111111-2222-4333-8444-555555555555"

        self.actor = SimpleNamespace(pk=7)
        self.msr = SimpleNamespace(
            pk=self.msr_id,
            number=2,
            status="APPROVED",
            project_id=self.project_id,
        )
        self.project = SimpleNamespace(
            pk=self.project_id,
            state="ACTIVE",
            current_approved=self.msr,
            current_approved_id=self.msr_id,
        )
        self.envelope = SimpleNamespace(
            project_id=self.project_id,
            approved_msr_id=self.msr_id,
            approved_msr_version="2",
        )

        self.project_query = patch.object(
            service.Project.objects, "select_for_update"
        )
        self.evidence_filter = patch.object(
            service.ProjectEvidence.objects, "filter"
        )
        self.evidence_create = patch.object(
            service.ProjectEvidence.objects, "create"
        )
        self.gate = patch.object(
            service, "_gate", return_value=self.actor
        )
        self.fingerprint = patch.object(
            service, "_fingerprint", return_value="a" * 64
        )
        self.audit = patch.object(service, "audit")

        query = self.project_query.start()
        self.addCleanup(self.project_query.stop)

        self.exists = self.evidence_filter.start()
        self.addCleanup(self.evidence_filter.stop)
        self.exists.return_value.exists.return_value = False

        self.create = self.evidence_create.start()
        self.addCleanup(self.evidence_create.stop)
        self.create.return_value = SimpleNamespace(pk="evidence-1")

        self.gate.start()
        self.addCleanup(self.gate.stop)

        self.fingerprint.start()
        self.addCleanup(self.fingerprint.stop)

        self.audit_call = self.audit.start()
        self.addCleanup(self.audit.stop)

        query.return_value.select_related.return_value.filter.return_value.first.return_value = self.project

    def authorize(self):
        return service.record_draft_intent(
            actor=self.actor,
            project_id=self.project_id,
            envelope=self.envelope,
            confirmed=True,
        )

    def test_valid_intent_is_recorded_without_provider_authority(self):
        result = self.authorize()

        self.assertEqual(result["status"], "DRAFT_INTENT_RECORDED")
        self.assertFalse(result["provider_request_authorized"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["provider_signature_verified"])
        self.assertFalse(result["project_completion_authorized"])

        self.create.assert_called_once()
        data = self.create.call_args.kwargs["data"]

        self.assertEqual(data["project_id"], self.project_id)
        self.assertEqual(data["msr_id"], self.msr_id)
        self.assertEqual(data["msr_version"], "2")
        self.assertEqual(data["draft_payload_sha256"], "a" * 64)
        self.assertFalse(data["provider_draft_created"])
        self.assertFalse(data["send_authorized"])
        self.audit_call.assert_called_once()

    def test_duplicate_authorization_is_rejected(self):
        self.exists.return_value.exists.return_value = True

        with self.assertRaises(ValidationError):
            self.authorize()

        self.create.assert_not_called()
        self.audit_call.assert_not_called()

    def test_other_project_envelope_is_rejected(self):
        self.envelope.project_id = (
            "99999999-2222-4333-8444-555555555555"
        )

        with self.assertRaises(ValidationError):
            self.authorize()

        self.create.assert_not_called()
        self.audit_call.assert_not_called()

    def test_other_msr_version_is_rejected(self):
        self.envelope.approved_msr_version = "1"

        with self.assertRaises(ValidationError):
            self.authorize()

        self.create.assert_not_called()
        self.audit_call.assert_not_called()

    def test_other_msr_is_rejected(self):
        self.envelope.approved_msr_id = (
            "99999999-2222-4333-8444-555555555555"
        )

        with self.assertRaises(ValidationError):
            self.authorize()

        self.create.assert_not_called()
        self.audit_call.assert_not_called()

    def test_explicit_confirmation_required(self):
        with self.assertRaises(ValidationError):
            service.record_draft_intent(
                actor=self.actor,
                project_id=self.project_id,
                envelope=self.envelope,
                confirmed=False,
            )

        self.create.assert_not_called()
        self.audit_call.assert_not_called()