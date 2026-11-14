from hashlib import sha256
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_attestation_manifest_4941 import (
    InstallationSigningManifest,
)
from .installation_attestation_pdf_4942 import (
    SIGNATURE_ANCHOR,
    DATE_ANCHOR,
    render_unsigned_installation_attestation,
)


MODULE = "core.installation_attestation_pdf_4942"
SOURCE = b"%PDF-1.4\nsynthetic inspection\n%%EOF\n"


def manifest():
    fields = dict(
        project_id="project-4942",
        approved_msr_id="msr-4942",
        approved_msr_version=1,
        preparation_evidence_id="prep-4942",
        source_evidence_id="source-4942",
        source_pdf_sha256=sha256(SOURCE).hexdigest(),
        source_pdf=SOURCE,
        signer_user_id="manager-4942",
        signer_email="installer@example.invalid",
        signer_name="Synthetic Installation Manager",
        attestation_binding_sha256="a" * 64,
    )
    identity = {
        "purpose": "DOCUSIGN_INSTALLATION_SIGNING_MANIFEST_4941",
        **{key: value for key, value in fields.items() if key != "source_pdf"},
        "source_document_role": "SUPPORTING_SOURCE_NOT_SIGNED",
    }
    fields["manifest_sha256"] = canonical_hash(identity)
    return InstallationSigningManifest(**fields)


class UnsignedAttestationPdfTests(TestCase):
    def setUp(self):
        self.patches = [
            patch(MODULE + ".settings"),
            patch(MODULE + ".build_installation_signing_manifest"),
        ]
        self.settings, self.builder = [p.start() for p in self.patches]
        self.addCleanup(self.stop_all)
        self.settings.ENVIRONMENT = "development"
        self.settings.DEBUG = True
        self.builder.return_value = manifest()

    def stop_all(self):
        for item in reversed(self.patches):
            item.stop()

    def render(self):
        return render_unsigned_installation_attestation(
            actor=SimpleNamespace(pk="ceo-4942"),
            project_id="project-4942",
        )

    def test_one_page_unsigned_document_has_binding_and_anchors(self):
        result = self.render()
        self.assertEqual(result.status, "UNSIGNED_INTERNAL_ATTESTATION")
        self.assertTrue(result.content.startswith(b"%PDF-"))
        self.assertTrue(result.content.rstrip().endswith(b"%%EOF"))
        self.assertEqual(sha256(result.content).hexdigest(), result.pdf_sha256)
        self.assertIn(SIGNATURE_ANCHOR.encode(), result.content)
        self.assertIn(DATE_ANCHOR.encode(), result.content)
        self.assertEqual(result.source_pdf_sha256, sha256(SOURCE).hexdigest())
        self.assertFalse(result.envelope_created)
        self.assertFalse(result.signature_verified)
        self.assertFalse(result.source_artifact_authenticated)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.completion_authorized)

    def test_pdf_generation_is_deterministic(self):
        self.assertEqual(self.render().pdf_sha256, self.render().pdf_sha256)

    def test_changed_source_fingerprint_rejected(self):
        changed = self.builder.return_value
        object.__setattr__(changed, "source_pdf_sha256", "0" * 64)
        with self.assertRaises(ValidationError):
            self.render()

    def test_changed_manifest_identity_rejected(self):
        changed = self.builder.return_value
        object.__setattr__(changed, "signer_user_id", "wrong-manager")
        with self.assertRaises(ValidationError):
            self.render()

    def test_claimed_provider_authentication_rejected(self):
        changed = self.builder.return_value
        object.__setattr__(changed, "signer_authenticated", True)
        with self.assertRaises(ValidationError):
            self.render()

    def test_production_environment_rejected(self):
        self.settings.ENVIRONMENT = "production"
        with self.assertRaises(PermissionDenied):
            self.render()

    def test_missing_signer_email_rejected(self):
        changed = self.builder.return_value
        object.__setattr__(changed, "signer_email", "")
        with self.assertRaises(ValidationError):
            self.render()
