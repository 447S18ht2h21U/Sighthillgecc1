"""Focused test-only equipment consistency between Invoice and Receipt."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .invoice_receipt_equipment_4515 import fictional_equipment_document


class InvoiceReceiptEquipment4515Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(__file__).resolve().parents[2]
        cls.paths = {
            "INVOICE": root / "docs/reference/GECC-20261107-final-seven"
                       / "GECC Invoice 20261107v4.pdf",
            "RECEIPT": root / "docs/reference/GECC-20261107-v4-survey-corrected"
                       / "GECC Receipt 20261107v4-survey-corrected.pdf",
        }

    def setUp(self):
        self.snapshot = {
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "TEST-HP-100",
                "description": "Fictional heat pump installation",
                "quantity": 1,
                "category_of_work": "New installation",
            }, {
                "brand": "Goodman",
                "residential_system_type": "Air Handler",
                "model_number": "TEST-AH-200",
                "description": "Fictional air handler installation",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
        }
        self.fields = {
            "customer_name": "FICTIONAL AVERY SAMPLE",
            "project_code": "TEST-001",
            "project_address": "123 Fictional Lane",
            "project_city": "Sample City",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "555-0100",
            "customer_email": "avery@example.invalid",
        }

    def render(self, kind, source=None):
        return fictional_equipment_document(
            self.paths[kind].read_bytes() if source is None else source,
            kind, self.snapshot, self.fields,
        )

    def test_invoice_descriptions(self):
        text = PdfReader(BytesIO(self.render("INVOICE"))).pages[0].extract_text()
        self.assertIn("Fictional heat pump installation", text)
        self.assertIn("Fictional air handler installation", text)

    def test_invoice_does_not_invent_model_numbers(self):
        text = PdfReader(BytesIO(self.render("INVOICE"))).pages[0].extract_text()
        self.assertNotIn("TEST-HP-100", text)
        self.assertNotIn("TEST-AH-200", text)

    def test_receipt_uses_actual_msr_model_numbers(self):
        text = PdfReader(BytesIO(self.render("RECEIPT"))).pages[0].extract_text()
        self.assertIn("TEST-HP-100", text)
        self.assertIn("TEST-AH-200", text)

    def test_receipt_retains_empty_serial_entries(self):
        text = PdfReader(BytesIO(self.render("RECEIPT"))).pages[0].extract_text()
        self.assertNotIn("SERIAL-FICTIONAL-999", text)
        self.assertIn("Serial Number", text)

    def test_both_forms_remain_one_page(self):
        for kind in self.paths:
            reader = PdfReader(BytesIO(self.render(kind)), strict=True)
            self.assertEqual(len(reader.pages), 1)
            self.assertFalse(reader.get_fields())

    def test_originals_and_snapshot_preserved(self):
        before = deepcopy(self.snapshot)
        for kind, path in self.paths.items():
            digest = sha256(path.read_bytes()).digest()
            self.render(kind)
            self.assertEqual(sha256(path.read_bytes()).digest(), digest)
        self.assertEqual(before, self.snapshot)

    def test_invalid_equipment_denied(self):
        self.snapshot["equipment"][0]["quantity"] = 0
        for kind in self.paths:
            with self.assertRaises(ValueError):
                self.render(kind)

    def test_tampered_pdf_denied(self):
        for kind, path in self.paths.items():
            with self.assertRaises(ValueError):
                self.render(kind, path.read_bytes() + b"tampered")
