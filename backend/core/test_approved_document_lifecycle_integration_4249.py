"""Real Django records, actual PDF renderers, and lifecycle integrity."""
from copy import deepcopy
from decimal import Decimal

from django.test import TestCase

from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_document_lifecycle_integration_4249 import (
    inspect_integrated_document_lifecycle,
)
from .models import Document, MSR
from .test_approved_document_real_pdfs_4245 import (
    RealRecordSixPDF4245Tests,
)


class RealLifecycleIntegration4249Tests(TestCase):
    def setUp(self):
        RealRecordSixPDF4245Tests.setUp(self)

    def prepare_no_promotion(self):
        snapshot = deepcopy(self.full_snapshot)
        snapshot.pop("other")
        self.assertEqual(
            Decimal(str(snapshot["discount"])), Decimal("150.00")
        )
        snapshot["discount"] = "0.00"
        snapshot["total_price"] = str(
            Decimal(str(snapshot["total_price"])) + Decimal("150.00")
        )

        successor = MSR.objects.create(
            project=self.project,
            number=3,
            status="DRAFT",
            source=self.full_msr,
            created_by=self.associate,
            prepared_by=self.associate,
            snapshot=snapshot,
        )
        successor.status = "APPROVED"
        successor.approved_by = self.comptroller
        successor.save(update_fields=["status", "approved_by"])

        self.project.current_approved = successor
        self.project.save(update_fields=["current_approved"])
        self.full_msr = successor

    def render(self):
        return RealRecordSixPDF4245Tests.render(self)

    def test_real_six_pdf_lifecycle_is_review_only(self):
        self.prepare_no_promotion()
        original = deepcopy(self.full_msr.snapshot)

        batch = self.render()
        report = inspect_integrated_document_lifecycle(batch)

        self.assertEqual(len(report.documents), 6)
        self.assertTrue(all(x.preview_verified for x in report.documents))
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.project_completion_authorized)
        self.assertTrue(all(
            not x.signed_evidence_verified
            and not x.customer_delivery_verified
            and not x.completion_evidence_verified
            for x in report.documents
        ))
        self.assertEqual(Document.objects.count(), 0)

        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, original)

    def test_modified_pdf_content_cannot_pass_lifecycle(self):
        self.prepare_no_promotion()
        batch = self.render()

        corrupted = {
            **batch,
            "pdfs": dict(batch["pdfs"]),
        }
        corrupted["pdfs"]["RECEIPT"] += b"altered-content"

        with self.assertRaises(LifecycleDenied):
            inspect_integrated_document_lifecycle(corrupted)

        self.assertEqual(Document.objects.count(), 0)