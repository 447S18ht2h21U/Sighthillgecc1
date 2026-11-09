"""Focused approved Receipt preview tests; no database."""
import os
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_receipt_overlay_preview_4223 import create_receipt_preview


class ApprovedReceiptPreviewTests(SimpleTestCase):
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
            "discount": "0.00",
            "tax": "500.00",
            "total_price": "10500.00",
        }

    def render(self):
        return create_receipt_preview(
            self.directory, self.snapshot,
            "TEST-PROJECT-4223",
            "TEST-INVOICE-4223",
            "2026-11-03",
        )

    def text(self):
        return PdfReader(BytesIO(self.render())).pages[0].extract_text()

    def test_single_page_receipt_pdf(self):
        self.assertEqual(
            len(PdfReader(BytesIO(self.render())).pages), 1
        )

    def test_customer_and_equipment_from_msr(self):
        text = self.text()
        self.assertIn("FICTIONAL CUSTOMER", text)
        self.assertIn("TEST-HP-100", text)
        self.assertIn("TEST-INVOICE-4223", text)

    def test_reconciled_amounts(self):
        text = self.text()
        self.assertIn("10,000.00", text)
        self.assertIn("500.00", text)
        self.assertIn("10,500.00", text)

    def test_explicitly_unverified_payment(self):
        text = self.text()
        self.assertIn("PAYMENT NOT VERIFIED", text)
        self.assertIn("FICTIONAL RECEIPT PREVIEW", text)

    def test_approved_customer_survey_preserved(self):
        text = self.text().lower()
        self.assertIn("clean up", text)
        self.assertIn("professional", text)
        self.assertIn("refer us", text)

    def test_mismatched_total_rejected(self):
        self.snapshot["total_price"] = "9999.00"
        with self.assertRaises(ValueError):
            self.render()

    def test_more_than_eight_equipment_rows_rejected(self):
        self.snapshot["equipment"] *= 9
        with self.assertRaises(ValueError):
            self.render()

    def test_promotion_notes_not_silently_discarded(self):
        self.snapshot["other"] = {
            "type": "Cash Back",
            "notes": "Company promotional benefit.",
            "amount": "100.00",
        }
        with self.assertRaises(ValueError):
            self.render()

    def test_original_and_msr_are_unchanged(self):
        original_snapshot = deepcopy(self.snapshot)
        original = self.directory / "GECC Receipt ref1103.pdf"
        before = sha256(original.read_bytes()).hexdigest()
        self.render()
        self.assertEqual(self.snapshot, original_snapshot)
        self.assertEqual(
            sha256(original.read_bytes()).hexdigest(), before
        )