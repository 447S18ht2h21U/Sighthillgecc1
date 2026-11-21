"""Step 5202: real retained source through offline authorization."""
import os
from hashlib import sha256
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.documents import canonical_hash
from core.models import AuditEvent, ProjectEvidence, Role, User
from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.installation_source_artifact_4826 import (
    retain_installation_source,
    verify_retained_installation_source,
)
from core.installation_attestation_record_4939 import (
    record_installation_attestation_preparation,
)
from core.installation_attestation_verifier_4940 import (
    verify_attestation_preparation,
)
from core.installation_attestation_manifest_4941 import (
    build_installation_signing_manifest,
)
from core.installation_draft_browser_5185 import assemble, authorize
from core.installation_draft_authorization_5179 import KIND

PDF = b"%PDF-1.4\nDisposable installation evidence 5202\n%%EOF\n"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class IndependentInstallationAcceptance5202(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def prepare_chain(self):
        self.ceo = User.objects.create_user(
            username="installation_5202_ceo",
            role=Role.CEO,
            initials="EC",
        )
        self.inspector.email = "inspection5202@example.invalid"
        self.inspector.first_name = "Installation"
        self.inspector.last_name = "Manager"
        self.inspector.save(
            update_fields=["email", "first_name", "last_name"]
        )

        inspection = self.capture()
        self.review(inspection)
        source = retain_installation_source(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_id=inspection.pk,
            content=PDF,
            description="Disposable retained installation inspection PDF.",
        )
        self.assertTrue(
            verify_retained_installation_source(self.project)
        )

        preparation, created = (
            record_installation_attestation_preparation(
                actor=self.ceo,
                project_id=self.project.pk,
            )
        )
        self.assertTrue(created)

        verified = verify_attestation_preparation(
            project_id=self.project.pk
        )
        self.assertTrue(verified.record_integrity_verified)
        self.assertTrue(verified.current_source_binding_verified)
        self.assertFalse(verified.provider_envelope_verified)
        self.assertFalse(verified.trusted_installation_evidence)

        manifest = build_installation_signing_manifest(
            actor=self.ceo,
            project_id=self.project.pk,
        )
        self.assertEqual(manifest.source_pdf, PDF)
        self.assertEqual(
            manifest.source_pdf_sha256, sha256(PDF).hexdigest()
        )
        self.assertEqual(
            manifest.source_evidence_id, str(source.pk)
        )
        self.assertEqual(
            manifest.preparation_evidence_id,
            str(preparation.pk),
        )
        self.assertFalse(manifest.signer_authenticated)
        self.assertFalse(manifest.completion_authorized)
        return source

    def test_real_chain_authorization_and_duplicate_rejection(self):
        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            self.prepare_chain()
            envelope = assemble(
                actor=self.ceo,
                project_id=self.project.pk,
            )
            self.assertEqual(
                envelope.project_id, str(self.project.pk)
            )
            self.assertIsNone(envelope.envelope_id)
            self.assertFalse(envelope.provider_signed)
            self.assertFalse(envelope.completion_authorized)

            before = AuditEvent.objects.count()
            result = authorize(
                actor=self.ceo,
                project_id=self.project.pk,
                confirmed=True,
            )
            self.assertEqual(
                result["status"], "DRAFT_INTENT_RECORDED"
            )
            self.assertEqual(
                AuditEvent.objects.count(), before + 1
            )

            record = ProjectEvidence.objects.get(
                pk=result["evidence_id"],
                kind=KIND,
                msr=self.msr,
            )
            self.assertEqual(
                record.digest, canonical_hash(record.data)
            )
            for field in (
                "provider_draft_created",
                "provider_request_authorized",
                "send_authorized",
                "provider_signature_verified",
                "inspection_findings_verified",
                "receipt_issuance_authorized",
                "project_completion_authorized",
            ):
                self.assertIs(record.data[field], False)

            with self.assertRaises(ValidationError):
                authorize(
                    actor=self.ceo,
                    project_id=self.project.pk,
                    confirmed=True,
                )
            self.assertEqual(
                ProjectEvidence.objects.filter(
                    msr=self.msr, kind=KIND
                ).count(), 1
            )
            self.assertEqual(
                AuditEvent.objects.count(), before + 1
            )

    def test_modified_retained_source_fails_closed(self):
        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            source = self.prepare_chain()
            altered = dict(source.data)
            altered["content_sha256"] = "0" * 64
            from django.db import IntegrityError, transaction

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    ProjectEvidence.objects.filter(pk=source.pk).update(
                        data=altered,
                        digest=canonical_hash(altered),
                    )

            source.refresh_from_db()
            self.assertEqual(
                source.data["content_sha256"],
                sha256(PDF).hexdigest(),
            )
            self.assertTrue(
                verify_retained_installation_source(self.project)
            )
            manifest = build_installation_signing_manifest(
                actor=self.ceo,
                project_id=self.project.pk,
            )
            self.assertEqual(manifest.source_pdf, PDF)
            self.assertFalse(manifest.trusted_installation_evidence)
            self.assertFalse(manifest.completion_authorized)
            self.assertFalse(
                ProjectEvidence.objects.filter(
                    msr=self.msr, kind=KIND
                ).exists()
            )
