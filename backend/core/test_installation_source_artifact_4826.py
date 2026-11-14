"""Isolated retention, integrity, and authority boundary acceptance."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .installation_source_artifact_4826 import (
    SOURCE_KIND,
    retain_installation_source,
    verify_retained_installation_source,
)
from .models import AuditEvent, ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationSource4826(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    PDF = b"%PDF-1.4\nSynthetic inspection evidence\n%%EOF"

    def retain(self, inspection, **changes):
        args = {
            "actor": self.inspector,
            "project_id": self.project.pk,
            "inspection_id": inspection.pk,
            "content": self.PDF,
            "description": "Synthetic physical-installation inspection PDF.",
        }
        return retain_installation_source(**(args | changes))

    def test_exact_artifact_retained_but_untrusted(self):
        inspection = self.capture()
        self.review(inspection)
        before = ProjectEvidence.objects.count()
        record = self.retain(inspection)
        self.assertEqual(ProjectEvidence.objects.count(), before + 1)
        self.assertEqual(record.kind, SOURCE_KIND)
        self.assertTrue(verify_retained_installation_source(self.project))
        self.assertFalse(record.data["source_authenticated"])
        self.assertFalse(record.data["trusted_installation_evidence"])
        self.assertFalse(record.data["final_receipt_issuance_authorized"])

    def test_duplicate_source_denied(self):
        inspection = self.capture()
        self.retain(inspection)
        with self.assertRaises(ValidationError):
            self.retain(inspection)
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=SOURCE_KIND
            ).count(), 1
        )

    def test_failed_inspection_cannot_retain_favorable_source(self):
        inspection = self.capture(inspection_passed=False)
        with self.assertRaises(ValidationError):
            self.retain(inspection)
        self.assertFalse(verify_retained_installation_source(self.project))

    def test_audit_failure_rolls_back_source_record(self):
        inspection = self.capture()
        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )
        with patch(
            "core.installation_source_artifact_4826.audit",
            side_effect=RuntimeError("Synthetic audit outage"),
        ):
            with self.assertRaises(RuntimeError):
                self.retain(inspection)
        self.assertEqual(before, (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        ))

    def test_malformed_artifact_rejected(self):
        inspection = self.capture()
        with self.assertRaises(ValidationError):
            self.retain(inspection, content=b"Not a PDF")
        self.assertFalse(verify_retained_installation_source(self.project))
