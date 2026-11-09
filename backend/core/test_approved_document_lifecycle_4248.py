"""Six-document lifecycle and evidence separation regressions."""
from dataclasses import replace
from types import SimpleNamespace

from django.test import SimpleTestCase

from .approved_document_lifecycle_4248 import (
    LifecycleDenied,
    inspect_fictional_document_lifecycle,
)
from .approved_six_document_batch_4236 import KINDS


class DocumentLifecycle4248Tests(SimpleTestCase):
    def setUp(self):
        self.batch = {
            "review_only": True,
            "release_authorized": False,
            "record": SimpleNamespace(
                review_only=True,
                release_authorized=False,
            ),
            "manifest": tuple(
                {
                    "kind": kind,
                    "status": "FICTIONAL_REVIEW_ONLY",
                }
                for kind in KINDS
            ),
            "pdfs": {kind: b"%PDF-test-only" for kind in KINDS},
        }

    def test_six_previews_never_grant_operational_authority(self):
        report = inspect_fictional_document_lifecycle(self.batch)
        self.assertEqual(len(report.documents), 6)
        self.assertTrue(report.review_only)
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.project_completion_authorized)
        for item in report.documents:
            self.assertTrue(item.preview_verified)
            self.assertFalse(item.operational_document_verified)
            self.assertFalse(item.signed_evidence_verified)
            self.assertFalse(item.customer_delivery_verified)
            self.assertFalse(item.completion_evidence_verified)

    def test_receipt_preview_not_customer_delivery(self):
        report = inspect_fictional_document_lifecycle(self.batch)
        receipt = next(
            item for item in report.documents
            if item.kind == "RECEIPT"
        )
        self.assertIsNone(receipt.legacy_kind)
        self.assertFalse(receipt.customer_delivery_verified)

    def test_completion_certificate_preview_not_docusign(self):
        report = inspect_fictional_document_lifecycle(self.batch)
        for item in report.documents:
            if item.kind.startswith("COMPLETION_"):
                self.assertFalse(item.signed_evidence_verified)
                self.assertFalse(item.completion_evidence_verified)

    def test_missing_document_denied(self):
        self.batch["pdfs"].pop("RECEIPT")
        with self.assertRaises(LifecycleDenied):
            inspect_fictional_document_lifecycle(self.batch)

    def test_wrong_manifest_order_denied(self):
        self.batch["manifest"] = tuple(
            reversed(self.batch["manifest"])
        )
        with self.assertRaises(LifecycleDenied):
            inspect_fictional_document_lifecycle(self.batch)

    def test_release_authority_denied(self):
        self.batch["release_authorized"] = True
        with self.assertRaises(LifecycleDenied):
            inspect_fictional_document_lifecycle(self.batch)

    def test_signed_or_released_record_denied(self):
        self.batch["record"] = replace(
            self.batch["record"]
        ) if hasattr(self.batch["record"], "__dataclass_fields__") else (
            SimpleNamespace(
                review_only=True,
                release_authorized=True,
            )
        )
        with self.assertRaises(LifecycleDenied):
            inspect_fictional_document_lifecycle(self.batch)

    def test_empty_pdf_denied(self):
        self.batch["pdfs"]["INVOICE"] = b""
        with self.assertRaises(LifecycleDenied):
            inspect_fictional_document_lifecycle(self.batch)