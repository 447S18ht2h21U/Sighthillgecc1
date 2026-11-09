"""One focused real-PDF integration pass for all six approved forms."""
import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from .approved_six_document_batch_4236 import (
    KINDS, build_six_document_review,
)
from .approved_document_preview_gateway_4235 import PreviewDenied
from .test_approved_sow_page_two_4232 import SOWPageTwo4232Tests


class SixRealDocuments4236Tests(SimpleTestCase):
    def setUp(self):
        fixture = SOWPageTwo4232Tests()
        fixture.setUp()
        self.snapshot = deepcopy(fixture.snapshot)
        self.reference = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )
        self.args = {
            "project_code": "TEST-PROJECT-4236",
            "msr_version": "4236-1",
            "created": "2026-11-04",
            "associate": "FICTIONAL ASSOCIATE",
            "invoice_number": "TEST-INVOICE-4236",
            "invoice_date": "2026-11-04",
        }

    def run_batch(self):
        return build_six_document_review(
            self.reference, self.snapshot, **self.args
        )

    def test_real_six_pdf_renderers_and_consistency(self):
        # A promotion requires a separately approved Receipt disclosure.
        # This success fixture deliberately contains no promotion.
        # The successful fictional batch contains no promotion.
        # Preserve the original promotion rejection safeguards.
        from decimal import Decimal
        self.snapshot.pop("other", None)
        discount = Decimal(str(self.snapshot["discount"]))
        self.snapshot["discount"] = "0.00"
        if discount != Decimal("150.00"):
            raise AssertionError("Unexpected fictional discount fixture.")
        original_total = Decimal(str(self.snapshot["total_price"]))
        self.snapshot["total_price"] = str(original_total + discount)
        before = deepcopy(self.snapshot)
        with patch.dict(os.environ, {
            "VERIDIAN_APPROVED_PDF_PREVIEW_GATE": "enabled-test-only",
            "VERIDIAN_ENVIRONMENT": "development",
            "GECC_DEV": "1",
        }):
            batch = self.run_batch()

        self.assertEqual(
            tuple(row["kind"] for row in batch["manifest"]), KINDS
        )
        self.assertEqual(len(batch["pdfs"]), 6)
        self.assertEqual(self.snapshot, before)
        self.assertFalse(batch["signed"])
        self.assertFalse(batch["released"])
        self.assertFalse(batch["customer_delivery"])

        for row in batch["manifest"]:
            self.assertGreater(row["pages"], 0)
            self.assertEqual(row["status"], "FICTIONAL_REVIEW_ONLY")
            print(
                "REAL PDF VERIFIED:",
                row["kind"], "pages=", row["pages"],
                "sha256=", row["sha256"],
            )

    def test_batch_rejected_with_gate_disabled(self):
        with patch.dict(os.environ, {
            "VERIDIAN_APPROVED_PDF_PREVIEW_GATE": "",
            "VERIDIAN_ENVIRONMENT": "development",
            "GECC_DEV": "1",
        }):
            with self.assertRaises(PreviewDenied):
                self.run_batch()

    def test_missing_financing_denied_before_rendering(self):
        self.snapshot.pop("financing_type")
        with self.assertRaises(PreviewDenied):
            self.run_batch()
    def test_promotion_receipt_disclosure_stays_blocked(self):
        before = deepcopy(self.snapshot)
        self.assertIn("other", self.snapshot)
        self.assertEqual(str(self.snapshot["discount"]), "150.00")
        with patch.dict(os.environ, {
            "VERIDIAN_APPROVED_PDF_PREVIEW_GATE": "enabled-test-only",
            "VERIDIAN_ENVIRONMENT": "development",
            "GECC_DEV": "1",
        }):
            with self.assertRaisesRegex(
                ValueError,
                "Promotion details require an approved Receipt disclosure"
            ):
                self.run_batch()
        self.assertEqual(self.snapshot, before)