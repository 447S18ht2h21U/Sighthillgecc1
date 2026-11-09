"""Focused Receipt alignment regression; no database writes."""
import os
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_receipt_overlay_preview_4223 import (
    EQUIPMENT_COLUMNS,
    AMOUNT_BASELINES,
    create_receipt_preview,
)


class ReceiptAlignment4225Tests(SimpleTestCase):
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
                    "description": "Fictional unit",
                    "quantity": 1,
                    "category_of_work": "New installation",
                },
                {
                    "brand": "Goodman",
                    "residential_system_type": "Air Handler",
                    "model_number": "TEST-AH-200",
                    "description": "Fictional unit",
                    "quantity": 1,
                    "category_of_work": "Replacing existing equipment",
                },
            ],
            "base_price": "10000.00",
            "discount": "0.00",
            "tax": "500.00",
            "total_price": "10500.00",
        }

    def render(self):
        return create_receipt_preview(
            self.directory, self.snapshot,
            "TEST-PROJECT-4225",
            "TEST-INVOICE-4225",
            "2026-11-03",
        )

    def test_equipment_positions_inside_column_boundaries(self):
        bounds = ((32,108), (108,181), (181,363), (363,473))
        for (_, x, width), (left, right) in zip(
            EQUIPMENT_COLUMNS, bounds
        ):
            self.assertGreaterEqual(x, left + 3)
            self.assertLessEqual(x + width, right - 3)

    def test_financial_row_baselines(self):
        self.assertEqual(
            AMOUNT_BASELINES,
            {
                "subtotal": 111,
                "sales_tax": 90,
                "other_charges": 69,
                "invoice_total": 48,
            },
        )

    def test_corrected_receipt_content_and_survey(self):
        text = PdfReader(BytesIO(self.render())).pages[0].extract_text()
        for expected in (
            "TEST-HP-100", "TEST-AH-200", "10,000.00",
            "500.00", "10,500.00",
            "PAYMENT NOT VERIFIED", "FICTIONAL RECEIPT PREVIEW",
        ):
            self.assertIn(expected, text)
        lower = text.lower()
        for expected in ("clean up", "professional", "refer us"):
            self.assertIn(expected, lower)

    def test_original_is_unchanged(self):
        source = self.directory / "GECC Receipt ref1103.pdf"
        before = sha256(source.read_bytes()).hexdigest()
        self.render()
        self.assertEqual(
            sha256(source.read_bytes()).hexdigest(), before
        )