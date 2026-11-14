from dataclasses import replace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from .models import (
    Role, User, InstallationInspectionEvidence4969,
)
from .test_receipt_feedback_db_4956 import (
    ReceiptFeedbackDatabaseAcceptance4956 as Fixture,
)
from .test_installation_docusign_evidence_intake_4966 import (
    inputs,
)
from .installation_docusign_evidence_intake_4966 import (
    assemble_unverified_inspection_evidence,
)
from .installation_evidence_retention_4969 import (
    retain_unverified_inspection_evidence,
    verify_retained_inspection_bytes,
    _bundle_material, _digest,
)

M = "core.installation_evidence_retention_4969"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionEvidenceDatabaseAcceptance4969(TestCase):
    def setUp(self):
        Fixture.setUp(self)
        self.manager = User.objects.create_user(
            username="inspection-manager-4969",
            password=None,
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )

        bundle = assemble_unverified_inspection_evidence(**inputs())
        bundle = replace(
            bundle,
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version=str(self.msr.number),
            signer_user_id=str(self.manager.pk),
        )
        self.bundle = replace(
            bundle,
            bundle_sha256=_digest(_bundle_material(bundle)),
        )

    def retain(self, bundle=None, actor=None):
        return retain_unverified_inspection_evidence(
            actor=actor or self.actor,
            project_id=self.project.pk,
            bundle=bundle or self.bundle,
        )

    def test_actual_insert_and_integrity_readback(self):
        with patch(M + ".audit"):
            record, created = self.retain()
        self.assertTrue(created)
        record = InstallationInspectionEvidence4969.objects.get(
            pk=record.pk
        )
        proof = verify_retained_inspection_bytes(record)
        self.assertTrue(proof["integrity_verified"])
        self.assertFalse(proof["provider_authenticated"])
        self.assertFalse(proof["completion_authorized"])
        self.assertEqual(bytes(record.signed_pdf), self.bundle.signed_pdf)

    def test_same_bundle_is_idempotent(self):
        with patch(M + ".audit"):
            first, created = self.retain()
            second, repeated = self.retain()
        self.assertTrue(created)
        self.assertFalse(repeated)
        self.assertEqual(first.pk, second.pk)

    def test_conflicting_bundle_cannot_replace_evidence(self):
        with patch(M + ".audit"):
            self.retain()
        changed = replace(
            self.bundle,
            negative_inspection_ids=("inspection_1",),
        )
        with self.assertRaises(ValidationError):
            self.retain(bundle=changed)
        self.assertEqual(
            InstallationInspectionEvidence4969.objects.count(), 1
        )

    def test_unverified_record_cannot_be_mutated(self):
        with patch(M + ".audit"):
            record, _ = self.retain()
        record.source_digest = "0" * 64
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()

    def test_audit_failure_rolls_back_retention(self):
        with patch(M + ".audit", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.retain()
        self.assertEqual(
            InstallationInspectionEvidence4969.objects.count(), 0
        )

    def test_nonmanager_signer_rejected(self):
        bundle = replace(
            self.bundle, signer_user_id=str(self.actor.pk)
        )
        bundle = replace(
            bundle, bundle_sha256=_digest(_bundle_material(bundle))
        )
        with self.assertRaises(ValidationError):
            self.retain(bundle=bundle)

    def test_corrupted_readback_rejected(self):
        with patch(M + ".audit"):
            record, _ = self.retain()
        record.certificate_sha256 = "0" * 64
        with self.assertRaises(ValidationError):
            verify_retained_inspection_bytes(record)
