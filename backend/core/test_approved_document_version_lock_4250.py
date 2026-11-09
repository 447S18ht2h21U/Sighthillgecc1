"""Actual PDFs and real approved MSR version-lock regressions."""
from dataclasses import replace

from django.test import TestCase

from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_document_version_lock_4250 import (
    inspect_version_locked_review,
)
from .models import Document
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class VersionLockedReview4250Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def render(self):
        return RealLifecycleIntegration4249Tests.render(self)

    def inspect(self, batch):
        return inspect_version_locked_review(
            project=self.project,
            msr=self.full_msr,
            batch=batch,
        )

    def test_current_approved_msr_and_pdfs_pass(self):
        batch = self.render()
        report = self.inspect(batch)
        self.assertEqual(len(report.documents), 6)
        self.assertFalse(report.project_completion_authorized)
        self.assertFalse(report.installation_authorized)
        self.assertEqual(Document.objects.count(), 0)

    def test_superseded_msr_review_is_rejected(self):
        batch = self.render()
        self.project.current_approved_id = None
        with self.assertRaises(LifecycleDenied):
            self.inspect(batch)

    def test_forged_snapshot_fingerprint_is_rejected(self):
        batch = self.render()
        forged = dict(batch)
        forged["record"] = replace(
            batch["record"],
            snapshot_sha256="0" * 64,
        )
        with self.assertRaises(LifecycleDenied):
            self.inspect(forged)

    def test_financing_classification_mismatch_is_rejected(self):
        batch = self.render()
        forged = dict(batch)
        forged["record"] = replace(
            batch["record"],
            financing_type="FINANCED",
        )
        with self.assertRaises(LifecycleDenied):
            self.inspect(forged)