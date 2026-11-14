from hashlib import sha256
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_attestation_manifest_4941 import (
    build_installation_signing_manifest,
)
from .installation_attestation_record_4939 import KIND
from .installation_source_artifact_4826 import SOURCE_KIND

M = "core.installation_attestation_manifest_4941"
PDF = b"%PDF-1.4\nsynthetic offline retained inspection\n%%EOF\n"


class InstallationManifestTests(TestCase):
    def setUp(self):
        self.patches = [
            patch(M + ".settings"),
            patch(M + ".User.objects"),
            patch(M + ".Project.objects"),
            patch(M + ".ProjectEvidence.objects"),
            patch(M + ".verify_attestation_preparation"),
        ]
        values = [item.start() for item in self.patches]
        self.addCleanup(self.stop_all)
        self.settings, self.users, self.projects, self.evidence, self.verifier = values
        self.settings.ENVIRONMENT = "development"
        self.settings.DEBUG = True

        self.actor = SimpleNamespace(pk="ceo-4941", role="CEO")
        self.signer = SimpleNamespace(
            pk="im-4941", role="INSTALLATION_MANAGER",
            email="installer@example.invalid",
            get_full_name=lambda: "Synthetic Installation Manager",
        )
        self.users.filter.return_value.first.side_effect = [
            self.actor, self.signer
        ]

        self.msr = SimpleNamespace(
            pk="msr-4941", project_id="project-4941",
            status="APPROVED", number=3, snapshot={"synthetic": True},
        )
        self.project = SimpleNamespace(
            pk="project-4941", state="ACTIVE",
            current_approved=self.msr, current_approved_id=self.msr.pk,
        )
        self.projects.select_related.return_value.filter.return_value.first.return_value = self.project

        self.source_data = {
            "recorder_id": self.signer.pk,
            "content_sha256": sha256(PDF).hexdigest(),
        }
        self.source = SimpleNamespace(
            pk="source-4941", msr_id=self.msr.pk,
            created_by_id=self.signer.pk,
            data=self.source_data,
            digest=canonical_hash(self.source_data),
        )
        self.preparation_data = {
            "source_evidence_id": str(self.source.pk),
            "source_pdf_sha256": sha256(PDF).hexdigest(),
            "binding_sha256": "b" * 64,
            "prepared_by_user_id": self.actor.pk,
            "signer_user_id": self.signer.pk,
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
        self.preparation = SimpleNamespace(
            pk="prep-4941", msr_id=self.msr.pk,
            created_by_id=self.actor.pk,
            data=self.preparation_data,
            digest=canonical_hash(self.preparation_data),
        )
        self.evidence.filter.side_effect = [
            [self.preparation], [self.source]
        ]
        self.verifier.return_value = SimpleNamespace(
            project_id=self.project.pk,
            msr_id=self.msr.pk,
            evidence_id=self.preparation.pk,
            source_evidence_id=self.source.pk,
            binding_sha256="b" * 64,
            record_integrity_verified=True,
            current_source_binding_verified=True,
            provider_envelope_verified=False,
            source_artifact_authenticated=False,
            trusted_installation_evidence=False,
            final_receipt_issuance_authorized=False,
            customer_delivery_verified=False,
            completion_authorized=False,
        )
        self.decode = patch(M + "._decode_artifact", return_value=PDF)
        self.decode_mock = self.decode.start()
        self.addCleanup(self.decode.stop)

    def stop_all(self):
        for item in reversed(self.patches):
            item.stop()

    def check(self):
        return build_installation_signing_manifest(
            actor=self.actor, project_id=self.project.pk
        )

    def test_manifest_binds_source_without_authentication(self):
        result = self.check()
        self.assertEqual(result.source_pdf, PDF)
        self.assertEqual(result.signer_user_id, self.signer.pk)
        self.assertEqual(result.signer_email, self.signer.email)
        self.assertEqual(result.source_pdf_sha256, sha256(PDF).hexdigest())
        self.assertEqual(len(result.manifest_sha256), 64)
        self.assertFalse(result.attestation_pdf_created)
        self.assertFalse(result.envelope_created)
        self.assertFalse(result.signer_authenticated)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.completion_authorized)

    def test_production_environment_rejected(self):
        self.settings.ENVIRONMENT = "production"
        with self.assertRaises(PermissionDenied):
            self.check()

    def test_untrusted_upstream_authority_rejected(self):
        self.verifier.return_value.source_artifact_authenticated = True
        with self.assertRaises(ValidationError):
            self.check()

    def test_duplicate_source_rejected(self):
        self.evidence.filter.side_effect = [
            [self.preparation], [self.source, self.source]
        ]
        with self.assertRaises(ValidationError):
            self.check()

    def test_preparation_digest_mismatch_rejected(self):
        self.preparation.digest = "0" * 64
        with self.assertRaises(ValidationError):
            self.check()

    def test_incorrect_signer_rejected(self):
        self.signer.role = "TECHNICIAN"
        with self.assertRaises(ValidationError):
            self.check()

    def test_pdf_content_mismatch_rejected(self):
        self.decode_mock.return_value = (
            b"%PDF-1.4\nwrong content\n%%EOF\n"
        )
        with self.assertRaises(ValidationError):
            self.check()
