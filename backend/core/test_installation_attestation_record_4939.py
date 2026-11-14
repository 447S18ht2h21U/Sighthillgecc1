from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_attestation_record_4939 import (
    KIND, PURPOSE, record_installation_attestation_preparation,
)

M = "core.installation_attestation_record_4939"


class AttestationRecordingTests(TestCase):
    def setUp(self):
        self.patches = [
            patch(M + ".User.objects"),
            patch(M + ".Project.objects"),
            patch(M + ".ProjectEvidence.objects"),
            patch(M + ".prepare_installation_attestation"),
            patch(M + ".audit"),
            patch(M + ".settings"),
            patch.dict(
                "os.environ",
                {"GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1"},
            ),
        ]
        mocks = [p.start() for p in self.patches]
        self.addCleanup(self.stop_all)
        self.users, self.projects, self.evidence = mocks[:3]
        self.binding, self.audit, self.settings = mocks[3:6]
        self.settings.ENVIRONMENT = "development"
        self.settings.DEBUG = True
        self.actor = SimpleNamespace(pk="ceo-4939", role="CEO")
        self.users.filter.return_value.first.return_value = self.actor
        self.msr = SimpleNamespace(
            pk="msr-4939", project_id="project-4939",
            status="APPROVED", number=2, snapshot={"x": 1},
        )
        self.project = SimpleNamespace(
            pk="project-4939", state="ACTIVE",
            current_approved=self.msr,
            current_approved_id=self.msr.pk,
        )
        self.projects.select_for_update.return_value.select_related.return_value.filter.return_value.first.return_value = self.project
        self.binding.return_value = SimpleNamespace(
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version=2,
            source_evidence_id="source-4939",
            source_pdf_sha256="a" * 64,
            binding_sha256="b" * 64,
            signer_user_id="manager-4939",
            prepared_by_user_id=self.actor.pk,
            provider="DOCUSIGN",
            status="OFFLINE_ATTESTATION_BINDING_NOT_SENT",
            provider_envelope_id=None,
            provider_authenticated=False,
            source_artifact_authenticated=False,
            trusted_installation_evidence=False,
            final_receipt_issuance_authorized=False,
            customer_delivery_verified=False,
            completion_authorized=False,
        )
        self.evidence.filter.return_value = []
        self.evidence.create.return_value = SimpleNamespace(pk="record-4939")

    def stop_all(self):
        for item in reversed(self.patches):
            item.stop()

    def run_preparation(self, **kwargs):
        return record_installation_attestation_preparation(
            actor=kwargs.pop("actor", self.actor),
            project_id="project-4939",
        )

    def test_persisted_binding_audited_without_trust(self):
        record, created = self.run_preparation()
        self.assertTrue(created)
        self.assertEqual(record.pk, "record-4939")
        fields = self.evidence.create.call_args.kwargs
        self.assertEqual(fields["kind"], KIND)
        self.assertEqual(fields["data"]["purpose"], PURPOSE)
        self.assertEqual(fields["data"]["source_pdf_sha256"], "a" * 64)
        self.assertEqual(fields["digest"], canonical_hash(fields["data"]))
        for key in (
            "envelope_created", "provider_authenticated",
            "source_artifact_authenticated", "trusted_installation_evidence",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified", "completion_authorized",
        ):
            self.assertIs(fields["data"][key], False)
        self.audit.assert_called_once()

    def test_same_preparation_is_idempotent(self):
        self.run_preparation()
        fields = self.evidence.create.call_args.kwargs
        existing = SimpleNamespace(
            pk="record-4939",
            msr_id=self.msr.pk,
            created_by_id=self.actor.pk,
            data=fields["data"],
            digest=fields["digest"],
        )
        self.evidence.filter.return_value = [existing]
        self.evidence.create.reset_mock()
        self.audit.reset_mock()
        returned, created = self.run_preparation()
        self.assertIs(returned, existing)
        self.assertFalse(created)
        self.evidence.create.assert_not_called()
        self.audit.assert_not_called()

    def test_conflicting_existing_binding_denied(self):
        self.evidence.filter.return_value = [
            SimpleNamespace(
                msr_id=self.msr.pk,
                created_by_id=self.actor.pk,
                data={"purpose": "different"},
                digest="0" * 64,
            )
        ]
        with self.assertRaises(ValidationError):
            self.run_preparation()
        self.evidence.create.assert_not_called()

    def test_duplicate_records_denied(self):
        self.evidence.filter.return_value = [object(), object()]
        with self.assertRaises(ValidationError):
            self.run_preparation()

    def test_missing_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            self.run_preparation(actor=None)

    def test_wrong_preparer_denied(self):
        self.actor.role = "INSTALLATION_MANAGER"
        with self.assertRaises(PermissionDenied):
            self.run_preparation()

    def test_production_disabled(self):
        self.settings.ENVIRONMENT = "production"
        with self.assertRaises(PermissionDenied):
            self.run_preparation()

    def test_upstream_trust_claim_denied(self):
        self.binding.return_value.provider_authenticated = True
        with self.assertRaises(ValidationError):
            self.run_preparation()
        self.evidence.create.assert_not_called()
