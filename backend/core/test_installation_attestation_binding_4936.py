import base64
import hashlib
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_attestation_binding_4936 import (
    prepare_installation_attestation,
)


M = "core.installation_attestation_binding_4936"
PDF = b"%PDF-1.4\nsynthetic inspection attestation\n%%EOF\n"


def setup_records():
    msr = SimpleNamespace(
        pk="msr-4936", project_id="project-4936",
        status="APPROVED", number=1,
        snapshot={"customer_email": "synthetic@example.invalid"}
    )
    project = SimpleNamespace(
        pk="project-4936", current_approved=msr,
        current_approved_id=msr.pk, state="ACTIVE"
    )
    schedule = SimpleNamespace(
        pk="schedule-4936", installation_manager_id="im-4936"
    )
    data = {
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "schedule_id": str(schedule.pk),
        "inspection_id": "inspection-4936",
        "inspection_digest": "a" * 64,
        "recorder_id": "im-4936",
        "content_base64": base64.b64encode(PDF).decode("ascii"),
        "content_sha256": hashlib.sha256(PDF).hexdigest(),
        "size_bytes": len(PDF),
        "source_authenticated": False,
        "trusted_installation_evidence": False,
        "final_receipt_issuance_authorized": False,
    }
    record = SimpleNamespace(
        pk="source-4936", msr_id=msr.pk,
        created_by_id="im-4936", data=data,
        digest=canonical_hash(data),
    )
    return project, schedule, record


class InstallationAttestationBindingTests(TestCase):
    def setUp(self):
        self.project, self.schedule, self.record = setup_records()
        patches = [
            patch(M + ".User.objects"),
            patch(M + ".Project.objects"),
            patch(M + ".ProjectEvidence.objects"),
            patch(M + "._completed_schedule", return_value=self.schedule),
            patch(M + ".verify_retained_installation_source", return_value=True),
            patch(M + ".settings"),
        ]
        self.addCleanup(self._stop_patches, patches)
        mocks = [p.start() for p in patches]
        self.users, self.projects, self.evidence = mocks[:3]
        self.schedule_check, self.verifier, self.settings = mocks[3:]
        self.settings.ENVIRONMENT = "development"
        self.settings.DEBUG = True
        self.preparer = SimpleNamespace(pk="ceo-4936", role="CEO")
        self.signer = SimpleNamespace(
            pk="im-4936", role="INSTALLATION_MANAGER"
        )
        self.users.filter.return_value.first.side_effect = [
            self.preparer, self.signer
        ]
        self.projects.select_related.return_value.filter.return_value.first.return_value = self.project
        self.evidence.filter.return_value = [self.record]
        self.actor = SimpleNamespace(pk="ceo-4936")

    @staticmethod
    def _stop_patches(patches):
        for p in reversed(patches):
            p.stop()

    def prepare(self, **kwargs):
        return prepare_installation_attestation(
            actor=kwargs.pop("actor", self.actor),
            project_id="project-4936",
            **kwargs
        )

    def test_verified_source_creates_offline_binding_without_authority(self):
        result = self.prepare()
        self.assertEqual(result.provider, "DOCUSIGN")
        self.assertEqual(result.signer_user_id, "im-4936")
        self.assertEqual(
            result.source_pdf_sha256, hashlib.sha256(PDF).hexdigest()
        )
        self.assertEqual(len(result.binding_sha256), 64)
        self.assertIsNone(result.provider_envelope_id)
        self.assertFalse(result.provider_authenticated)
        self.assertFalse(result.source_artifact_authenticated)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

    def test_missing_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            self.prepare(actor=None)

    def test_unauthorized_preparer_denied(self):
        self.preparer.role = "TECHNICIAN"
        with self.assertRaises(PermissionDenied):
            self.prepare()

    def test_live_mode_denied(self):
        with self.assertRaises(PermissionDenied):
            self.prepare(mode="LIVE")

    def test_production_environment_denied(self):
        self.settings.ENVIRONMENT = "production"
        with self.assertRaises(PermissionDenied):
            self.prepare()

    def test_unverified_retained_source_denied(self):
        self.verifier.return_value = False
        with self.assertRaises(ValidationError):
            self.prepare()

    def test_wrong_installation_manager_denied(self):
        self.record.created_by_id = "different-manager"
        with self.assertRaises(ValidationError):
            self.prepare()

    def test_tampered_source_denied(self):
        self.record.data["content_sha256"] = "0" * 64
        self.record.digest = canonical_hash(self.record.data)
        with self.assertRaises(ValidationError):
            self.prepare()

    def test_duplicate_source_denied(self):
        self.evidence.filter.return_value = [
            self.record, self.record
        ]
        with self.assertRaises(ValidationError):
            self.prepare()

    def test_cancelled_project_denied(self):
        self.project.state = "CANCELLED"
        with self.assertRaises(ValidationError):
            self.prepare()
