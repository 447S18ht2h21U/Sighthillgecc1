"""Focused fictional Invoice overlay tests; no database."""
import os
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_invoice_overlay_preview_4220 import (
    create_invoice_preview,
)


class ApprovedInvoiceOverlayPreviewTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )
        cls.snapshot = {
            "customer": "FICTIONAL SAMPLE CUSTOMER",
            "billing_address": "100 Sample Lane",
            "project_location": "100 Sample Lane",
            "project_city": "Baltimore",
            "project_state": "MD",
            "project_zip": "21201",
            "customer_phone": "555-0100",
            "customer_email": "sample@example.com",
            "equipment": [],
        }

    def preview(self, snapshot=None):
        return create_invoice_preview(
            self.reference,
            self.snapshot if snapshot is None else snapshot,
            "TEST-PROJECT-4220",
            "TEST-INVOICE-4220",
            "2026-11-03",
        )

    def test_preview_is_valid_single_page_pdf(self):
        pdf = PdfReader(BytesIO(self.preview()))
        self.assertEqual(len(pdf.pages), 1)

    def test_preview_contains_fictional_data(self):
        text = PdfReader(
            BytesIO(self.preview())
        ).pages[0].extract_text()
        self.assertIn("FICTIONAL SAMPLE CUSTOMER", text)
        self.assertIn("TEST-INVOICE-4220", text)
        self.assertIn("FICTIONAL DEVELOPMENT PREVIEW", text)

    def test_missing_customer_is_rejected(self):
        snapshot = dict(self.snapshot)
        snapshot["customer"] = ""
        with self.assertRaises(ValueError):
            self.preview(snapshot)

    def test_overlong_customer_is_rejected(self):
        snapshot = dict(self.snapshot)
        snapshot["customer"] = "X" * 160
        with self.assertRaises(ValueError):
            self.preview(snapshot)

    def test_non_ascii_text_is_rejected(self):
        snapshot = dict(self.snapshot)
        snapshot["customer"] = "Sample \u2603"
        with self.assertRaises(ValueError):
            self.preview(snapshot)

    def test_original_invoice_is_unchanged(self):
        from hashlib import sha256
        original = self.reference / "GECC Invoice ref1103.pdf"
        before = sha256(original.read_bytes()).hexdigest()
        self.preview()
        after = sha256(original.read_bytes()).hexdigest()
        self.assertEqual(before, after)