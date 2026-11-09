"""Real fictional MSR through six approved document-preview lifecycle checks.

Only the disposable Django in-memory test database is used.
No live document release, signing, sending, or completion is performed.
"""
from copy import deepcopy

from django.test import TestCase

from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_document_lifecycle_integration_4249 import (
    inspect_integrated_document_lifecycle,
)
from .approved_project_workflow_checklist_4251 import (
    inspect_project_workflow_checklist,
)
from .models import Document, MSR
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class MockCustomerDocuments4268Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def render_six(self):
        batch = RealLifecycleIntegration4249Tests.render(self)
        self.assertEqual(len(batch["pdfs"]), 6)
        return batch

    def test_six_previews_bind_to_current_approved_msr(self):
        original = deepcopy(self.full_msr.snapshot)

        self.project.refresh_from_db()
        self.assertEqual(
            self.project.current_approved_id, self.full_msr.pk
        )
        self.assertEqual(self.full_msr.status, "APPROVED")

        batch = self.render_six()
        checklist = inspect_project_workflow_checklist(
            project=self.project,
            msr=self.full_msr,
            batch=batch,
        )

        self.assertEqual(checklist.msr_version, self.full_msr.number)
        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, original)
        self.assertEqual(Document.objects.count(), 0)

    def test_verified_previews_do_not_establish_delivery(self):
        batch = self.render_six()
        report = inspect_integrated_document_lifecycle(batch)

        self.assertEqual(len(report.documents), 6)
        self.assertTrue(all(
            item.preview_verified for item in report.documents
        ))
        self.assertTrue(all(
            not item.signed_evidence_verified
            and not item.customer_delivery_verified
            and not item.completion_evidence_verified
            for item in report.documents
        ))
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.project_completion_authorized)
        self.assertEqual(Document.objects.count(), 0)

    def test_modified_receipt_fails_full_workflow_review(self):
        batch = self.render_six()
        corrupted = {
            **batch,
            "pdfs": dict(batch["pdfs"]),
        }
        corrupted["pdfs"]["RECEIPT"] += b"unauthorized-change"

        with self.assertRaises(LifecycleDenied):
            inspect_project_workflow_checklist(
                project=self.project,
                msr=self.full_msr,
                batch=corrupted,
            )

        self.assertEqual(Document.objects.count(), 0)