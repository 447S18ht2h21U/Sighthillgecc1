"""Real-record checklist tests with actual approved PDF previews."""
from dataclasses import replace

from django.test import TestCase

from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_project_workflow_checklist_4251 import (
    inspect_project_workflow_checklist,
)
from .models import Document
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class ProjectWorkflowChecklist4251Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def render(self):
        return RealLifecycleIntegration4249Tests.render(self)

    def inspect(self, batch):
        return inspect_project_workflow_checklist(
            project=self.project,
            msr=self.full_msr,
            batch=batch,
        )

    def test_real_project_creates_safe_checklist(self):
        result = self.inspect(self.render())
        self.assertEqual(result.document_count, 6)
        self.assertEqual(result.msr_id, str(self.full_msr.pk))
        self.assertEqual(result.msr_version, 3)
        self.assertTrue(result.review_only)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.project_completion_authorized)
        self.assertEqual(
            [item.status for item in result.items],
            ["VERIFIED", "VERIFIED_REVIEW_ONLY"] +
            ["NOT_EVALUATED"] * 4,
        )
        self.assertEqual(Document.objects.count(), 0)

    def test_outdated_msr_cannot_produce_checklist(self):
        batch = self.render()
        self.project.current_approved_id = None
        with self.assertRaises(LifecycleDenied):
            self.inspect(batch)

    def test_corrupted_receipt_cannot_produce_checklist(self):
        batch = self.render()
        corrupted = {**batch, "pdfs": dict(batch["pdfs"])}
        corrupted["pdfs"]["RECEIPT"] += b"changed"
        with self.assertRaises(LifecycleDenied):
            self.inspect(corrupted)

    def test_forged_review_identity_cannot_produce_checklist(self):
        batch = self.render()
        forged = {
            **batch,
            "record": replace(batch["record"], msr_id="wrong-msr"),
        }
        with self.assertRaises(LifecycleDenied):
            self.inspect(forged)