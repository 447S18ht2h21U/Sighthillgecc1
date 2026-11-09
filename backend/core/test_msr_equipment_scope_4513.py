"""Isolated fictional equipment and scope population tests."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .msr_equipment_scope_4513 import fictional_equipment_scope_preview


class MSREquipment4513Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = (
            Path(__file__).resolve().parents[2]
            / "docs/reference/GECC-20261107-final-seven"
            / "GECC Project Scope of Work 20261107v2.pdf"
        )

    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL AVERY SAMPLE",
            "billing_address": "123 Fictional Lane",
            "project_location": "123 Fictional Lane",
            "project_city": "Sample City",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "555-0100",
            "customer_email": "avery@example.invalid",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "TEST-HP-100",
                "description": "Fictional HVAC equipment",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
            "description_of_work": "New installation",
            "scope": "Install fictional HVAC system.",
            "financing_type": "FINANCED",
            "payment_method": "EFT",
            "base_price": "12000.00",
            "discount": "1000.00",
            "tax": "0.00",
            "total_price": "11000.00",
            "other": {
                "type": "Marketing Promotion",
                "amount": "1000.00",
                "notes": "Fictional retail price discount",
            },
        }

    def render(self):
        return fictional_equipment_scope_preview(
            self.reference.read_bytes(), self.snapshot,
            "TEST-001", "V1", "2026-11-08",
            "FICTIONAL SALES ASSOCIATE",
        )

    def test_brand_type_and_scope_present(self):
        pdf = PdfReader(BytesIO(self.render()), strict=True)
        text = pdf.pages[0].extract_text()
        for item in ("Goodman", "Heat Pump", "Install fictional HVAC system."):
            self.assertIn(item, text)

    def test_two_pages_and_no_form_fields(self):
        pdf = PdfReader(BytesIO(self.render()), strict=True)
        self.assertEqual(len(pdf.pages), 2)
        self.assertFalse(pdf.get_fields())

    def test_commercial_summary_preserved(self):
        pdf = PdfReader(BytesIO(self.render()), strict=True)
        text = pdf.pages[1].extract_text()
        self.assertIn("11,000.00", text)
        self.assertIn("YES", text)

    def test_invalid_work_category_denied(self):
        self.snapshot["description_of_work"] = "Unknown work"
        with self.assertRaises(ValueError):
            self.render()

    def test_invalid_equipment_denied(self):
        self.snapshot["equipment"][0]["quantity"] = 0
        with self.assertRaises(ValueError):
            self.render()

    def test_more_than_eight_rows_denied(self):
        self.snapshot["equipment"] *= 9
        with self.assertRaises(ValueError):
            self.render()

    def test_oversized_scope_denied(self):
        self.snapshot["scope"] = "Fictional scope " * 40
        with self.assertRaises(ValueError):
            self.render()

    def test_source_and_pdf_unchanged(self):
        snapshot_before = deepcopy(self.snapshot)
        pdf_before = sha256(self.reference.read_bytes()).digest()
        self.render()
        self.assertEqual(snapshot_before, self.snapshot)
        self.assertEqual(pdf_before, sha256(self.reference.read_bytes()).digest())
