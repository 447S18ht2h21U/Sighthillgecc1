"""Focused commercial projection and preview regression."""
import os
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_sow_commercial_4231 import (
    sow_commercial_projection, make_sow_commercial_review,
)


class SOWCommercial4231Tests(SimpleTestCase):
    def setUp(self):
        self.reference = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )
        self.snapshot = {
            "customer": "FICTIONAL CUSTOMER",
            "billing_address": "100 Example Road",
            "project_location": "100 Example Road",
            "project_city": "Baltimore",
            "project_state": "MD",
            "project_zip": "21201",
            "customer_phone": "555-0100",
            "customer_email": "sample@example.com",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "TEST-HP-100",
                "description": "Fictional equipment",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
            "description_of_work": "New installation",
            "scope": "Install the fictional heat pump and test operation.",
            "financing_type": "NON_FINANCED",
            "base_price": "10000.00",
            "discount": "150.00",
            "tax": "500.00",
            "total_price": "10350.00",
            "other": {
                "type": "Reduced Price",
                "amount": "150.00",
                "notes": "Approved fictional price reduction.",
            },
        }

    def review(self):
        return make_sow_commercial_review(
            self.reference, self.snapshot,
            "TEST-PROJECT-4231", "4231-1",
            "2026-11-04", "FICTIONAL ASSOCIATE"
        )

    def test_reconciled_commercial_values(self):
        values = sow_commercial_projection(self.snapshot)
        self.assertEqual(values["total"], "10,350.00")
        self.assertEqual(values["other_charges"], "-150.00")
        self.assertEqual(values["description_of_work"], "New installation")

    def test_preview_contains_three_pages_and_review_data(self):
        pdf = PdfReader(BytesIO(self.review()), strict=True)
        self.assertEqual(len(pdf.pages), 3)
        text = pdf.pages[2].extract_text()
        for value in ("FICTIONAL CUSTOMER", "10,350.00",
                      "price reduction", "DO NOT SIGN"):
            self.assertIn(value, text)

    def test_price_mismatch_denied(self):
        self.snapshot["total_price"] = "9000.00"
        with self.assertRaises(ValueError):
            sow_commercial_projection(self.snapshot)

    def test_unapproved_work_type_denied(self):
        self.snapshot["description_of_work"] = "Unapproved"
        with self.assertRaises(ValueError):
            sow_commercial_projection(self.snapshot)

    def test_cash_back_not_automatically_deducted(self):
        self.snapshot["other"]["type"] = "Cash Back"
        with self.assertRaises(ValueError):
            sow_commercial_projection(self.snapshot)

    def test_source_snapshot_not_mutated(self):
        before = deepcopy(self.snapshot)
        self.review()
        self.assertEqual(self.snapshot, before)