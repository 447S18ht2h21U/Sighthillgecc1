"""Focused Invoice commercial overlay tests, no database access."""
import os
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_invoice_commercial_preview_4222 import (
    create_commercial_invoice_preview,
)


class InvoiceCommercialPreviewTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )

    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL CUSTOMER",
            "billing_address": "100 Sample Lane",
            "project_location": "100 Sample Lane",
            "project_city": "Baltimore",
            "project_state": "MD",
            "project_zip": "21201",
            "customer_phone": "555-0100",
            "customer_email": "sample@example.com",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "TEST-HP-100",
                "description": "Fictional heat pump",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
            "base_price": "10000.00",
            "discount": "150.00",
            "tax": "500.00",
            "total_price": "10350.00",
            "other": {
                "type": "Reduced Price",
                "notes": "Approved fictional price reduction.",
                "amount": "150.00",
            },
        }

    def render(self):
        return create_commercial_invoice_preview(
            self.directory,
            self.snapshot,
            "TEST-PROJECT-4222",
            "TEST-INVOICE-4222",
            "2026-11-03",
        )

    def test_one_page_pdf_with_customer_and_equipment(self):
        pdf = PdfReader(BytesIO(self.render()))
        self.assertEqual(len(pdf.pages), 1)
        text = pdf.pages[0].extract_text()
        self.assertIn("FICTIONAL CUSTOMER", text)
        self.assertIn("TEST-HP-100", text)

    def test_reconciled_commercial_amounts(self):
        text = PdfReader(
            BytesIO(self.render())
        ).pages[0].extract_text()
        for amount in ("10,000.00", "500.00", "-150.00", "10,350.00"):
            self.assertIn(amount, text)

    def test_approved_notes_are_included(self):
        text = PdfReader(
            BytesIO(self.render())
        ).pages[0].extract_text()
        self.assertIn("Approved fictional price reduction.", text)

    def test_wrong_total_is_rejected(self):
        self.snapshot["total_price"] = "9999.00"
        with self.assertRaises(ValueError):
            self.render()

    def test_other_discount_mismatch_is_rejected(self):
        self.snapshot["other"]["amount"] = "200.00"
        with self.assertRaises(ValueError):
            self.render()

    def test_cash_back_does_not_silently_reduce_price(self):
        self.snapshot["other"]["type"] = "Cash Back"
        with self.assertRaises(ValueError):
            self.render()

    def test_free_equipment_does_not_silently_reduce_price(self):
        self.snapshot["other"]["type"] = "Free Water Heater"
        with self.assertRaises(ValueError):
            self.render()

    def test_non_price_promotion_without_discount_is_allowed(self):
        self.snapshot["other"]["type"] = "Cash Back"
        self.snapshot["discount"] = "0.00"
        self.snapshot["total_price"] = "10500.00"
        text = PdfReader(
            BytesIO(self.render())
        ).pages[0].extract_text()
        self.assertIn("Cash Back:", text)
        self.assertIn("10,500.00", text)

    def test_snapshot_and_original_pdf_remain_unchanged(self):
        from hashlib import sha256
        original_snapshot = deepcopy(self.snapshot)
        original_pdf = self.directory / "GECC Invoice ref1103.pdf"
        original_hash = sha256(original_pdf.read_bytes()).hexdigest()
        self.render()
        self.assertEqual(self.snapshot, original_snapshot)
        self.assertEqual(
            sha256(original_pdf.read_bytes()).hexdigest(),
            original_hash,
        )

    def test_excessive_notes_are_rejected_without_truncation(self):
        self.snapshot["other"]["notes"] = "LONG DESCRIPTION " * 30
        with self.assertRaises(ValueError):
            self.render()