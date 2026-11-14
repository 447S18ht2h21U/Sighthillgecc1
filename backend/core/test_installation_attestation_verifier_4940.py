from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from .documents import canonical_hash
from .installation_attestation_record_4939 import KIND, PURPOSE
from .installation_attestation_verifier_4940 import (
    verify_attestation_preparation,
)


M = "core.installation_attestation_verifier_4940"


class AttestationReadbackTests(TestCase):
    def setUp(self):
        self.patches = [
            patch(M + ".Project.objects"),
            patch(M + ".ProjectEvidence.objects"),
            patch(M + ".User.objects"),
            patch(M + ".prepare_installation_attestation"),
            patch(M + ".settings"),
        ]
        mocks = [p.start() for p in self.patches]
        self.addCleanup(self.stop_all)
        self.projects, self.evidence, self.users, self.binding, self.settings = mocks
        self.settings.ENVIRONMENT = "development"
        self.settings.DEBUG = True
        self.msr = SimpleNamespace(
            pk="msr-4940", project_id="project-4940",
            number=2, status="APPROVED", snapshot={"x": 1}
        )
        self.project = SimpleNamespace(
            pk="project-4940", state="ACTIVE",
            current_approved=self.msr, current_approved_id=self.msr.pk
        )
        self.projects.select_related.return_value.filter.return_value.first.return_value = self.project
        self.preparer = SimpleNamespace(pk="ceo-4940", role="CEO")
        self.users.filter.return_value.first.return_value = self.preparer
        self.binding.return_value = SimpleNamespace(
            status="OFFLINE_ATTESTATION_BINDING_NOT_SENT",
            provider="DOCUSIGN",
            provider_envelope_id=None,
            provider_authenticated=False,
            source_artifact_authenticated=False,
            trusted_installation_evidence=False,
            final_receipt_issuance_authorized=False,
            customer_delivery_verified=False,
            completion_authorized=False,
            source_evidence_id="source-4940",
            source_pdf_sha256="a" * 64,
            binding_sha256="b" * 64,
            signer_user_id="manager-4940",
        )
        self.payload = {
            "purpose": PURPOSE,
            "project_id": self.project.pk,
            "msr_id": self.msr.pk,
            "msr_version": self.msr.number,
            "source_evidence_id": "source-4940",
            "source_pdf_sha256": "a" * 64,
            "binding_sha256": "b" * 64,
            "signer_user_id": "manager-4940",
            "prepared_by_user_id": self.preparer.pk,
            "provider": "DOCUSIGN",
            "status": "OFFLINE_ATTESTATION_BINDING_NOT_SENT",
            "envelope_created": False,
            "provider_authenticated": False,
            "source_artifact_authenticated": False,
            "trusted_installation_evidence": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }
        self.record = SimpleNamespace(
            pk="record-4940", msr_id=self.msr.pk,
            created_by_id=self.preparer.pk, data=self.payload,
            digest=canonical_hash(self.payload),
        )
        self.evidence.filter.return_value = [self.record]

    def stop_all(self):
        for item in reversed(self.patches):
            item.stop()

    def check(self):
        return verify_attestation_preparation(project_id=self.project.pk)

    def test_matching_readback_verifies_without_provider_authority(self):
        result = self.check()
        self.assertTrue(result.record_integrity_verified)
        self.assertTrue(result.current_source_binding_verified)
        self.assertEqual(result.status, "PREPARATION_VERIFIED_NOT_SIGNED")
        self.assertFalse(result.provider_envelope_verified)
        self.assertFalse(result.source_artifact_authenticated)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

    def test_missing_preparation_denied(self):
        self.evidence.filter.return_value = []
        with self.assertRaises(ValidationError):
            self.check()

    def test_duplicate_preparation_denied(self):
        self.evidence.filter.return_value = [self.record, self.record]
        with self.assertRaises(ValidationError):
            self.check()

    def test_tampered_digest_denied(self):
        self.record.digest = "0" * 64
        with self.assertRaises(ValidationError):
            self.check()

    def test_tampered_source_fingerprint_denied(self):
        self.payload["source_pdf_sha256"] = "0" * 64
        self.record.digest = canonical_hash(self.payload)
        with self.assertRaises(ValidationError):
            self.check()

    def test_changed_original_signer_denied(self):
        self.binding.return_value.signer_user_id = "other-manager"
        with self.assertRaises(ValidationError):
            self.check()

    def test_claimed_provider_authentication_denied(self):
        self.payload["provider_authenticated"] = True
        self.record.digest = canonical_hash(self.payload)
        with self.assertRaises(ValidationError):
            self.check()

    def test_cancelled_project_denied(self):
        self.project.state = "CANCELLED"
        with self.assertRaises(ValidationError):
            self.check()

    def test_unauthorized_original_preparer_denied(self):
        self.preparer.role = "TECHNICIAN"
        with self.assertRaises(ValidationError):
            self.check()

    def test_production_disabled(self):
        self.settings.ENVIRONMENT = "production"
        with self.assertRaises(ValidationError):
            self.check()
