"""Focused eight-row Invoice preview tests, no database."""
import os
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_invoice_equipment_preview_4221 import (
    create_equipment_invoice_preview,
)


class InvoiceEquipmentPreviewTests(SimpleTestCase):
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
            "equipment": [
                {
                    "brand": "Goodman",
                    "residential_system_type": "Heat Pump",
                    "model_number": "TEST-HP-100",
                    "description": "Fictional heat pump",
                    "quantity": 1,
                    "category_of_work": "New installation",
                },
                {
                    "brand": "Goodman",
                    "residential_system_type": "Air Handler",
                    "model_number": "TEST-AH-200",
                    "description": "Fictional air handler",
                    "quantity": 1,
                    "category_of_work": "Replacing existing equipment",
                },
            ],
        }

    def render(self):
        return create_equipment_invoice_preview(
            self.directory, self.snapshot,
            "TEST-PROJECT-4221", "TEST-INVOICE-4221",
            "2026-11-03",
        )

    def test_pdf_has_one_page(self):
        self.assertEqual(
            len(PdfReader(BytesIO(self.render())).pages), 1
        )

    def test_approved_equipment_values_are_present(self):
        text = PdfReader(
            BytesIO(self.render())
        ).pages[0].extract_text()
        self.assertIn("Goodman", text)
        self.assertIn("TEST-HP-100", text)
        self.assertIn("TEST-AH-200", text)
        self.assertIn("FICTIONAL CUSTOMER", text)

    def test_invalid_category_rejected(self):
        self.snapshot["equipment"][0]["category_of_work"] = "Unknown"
        with self.assertRaises(ValueError):
            self.render()

    def test_more_than_eight_rows_rejected(self):
        self.snapshot["equipment"] *= 5
        with self.assertRaises(ValueError):
            self.render()

    def test_no_serial_or_price_is_invented(self):
        text = PdfReader(
            BytesIO(self.render())
        ).pages[0].extract_text()
        self.assertNotIn("SERIAL-12345", text)
        self.assertNotIn("$999.00", text)

    def test_original_source_is_preserved(self):
        from hashlib import sha256
        path = self.directory / "GECC Invoice ref1103.pdf"
        before = sha256(path.read_bytes()).hexdigest()
        self.render()
        self.assertEqual(before, sha256(path.read_bytes()).hexdigest())