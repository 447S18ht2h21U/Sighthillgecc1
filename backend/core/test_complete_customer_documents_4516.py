"""Fictional combined document checks; no DB or provider actions."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .complete_customer_documents_4516 import complete_fictional_document


class CompleteDocuments4516Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(__file__).resolve().parents[2]
        cls.paths = {
            "INVOICE": root / "docs/reference/GECC-20261107-final-seven/GECC Invoice 20261107v4.pdf",
            "RECEIPT": root / "docs/reference/GECC-20261107-v4-survey-corrected/GECC Receipt 20261107v4-survey-corrected.pdf",
        }

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
                "description": "Fictional heat pump installation",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
            "description_of_work": "New installation",
            "scope": "Fictional HVAC installation.",
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

    def render(self, kind, source=None, number="FICTIONAL-INV-001"):
        return complete_fictional_document(
            self.paths[kind].read_bytes() if source is None else source,
            kind, self.snapshot, "TEST-001", "V1",
            number, "2026-11-08",
        )

    def test_both_docs_include_commercial_totals(self):
        for kind in self.paths:
            text = PdfReader(BytesIO(self.render(kind))).pages[0].extract_text()
            for item in ("12,000.00", "-1,000.00", "11,000.00"):
                with self.subTest(kind=kind, value=item):
                    self.assertIn(item, text)

    def test_customer_and_invoice_ids_match(self):
        for kind in self.paths:
            text = PdfReader(BytesIO(self.render(kind))).pages[0].extract_text()
            self.assertIn("FICTIONAL AVERY SAMPLE", text)
            self.assertIn("FICTIONAL-INV-001", text)
            self.assertIn("TEST-001", text)

    def test_equipment_content_varies_by_document(self):
        invoice = PdfReader(BytesIO(self.render("INVOICE"))).pages[0].extract_text()
        receipt = PdfReader(BytesIO(self.render("RECEIPT"))).pages[0].extract_text()
        self.assertIn("Fictional heat pump installation", invoice)
        self.assertIn("TEST-HP-100", receipt)
        self.assertNotIn("TEST-HP-100", invoice)

    def test_receipt_does_not_assert_payment(self):
        text = PdfReader(BytesIO(self.render("RECEIPT"))).pages[0].extract_text()
        self.assertIn("NOT PAYMENT OR APPROVAL EVIDENCE", text)

    def test_cash_back_does_not_change_retail_price(self):
        self.snapshot["discount"] = "0.00"
        self.snapshot["total_price"] = "12000.00"
        self.snapshot["other"] = {
            "type": "Cash Back", "amount": "1000.00",
            "notes": "Fictional customer benefit",
        }
        for kind in self.paths:
            text = PdfReader(BytesIO(self.render(kind))).pages[0].extract_text()
            self.assertIn("12,000.00", text)
            self.assertNotIn("-1,000.00", text)

    def test_fabricated_invoice_number_rejected(self):
        with self.assertRaises(ValueError):
            self.render("INVOICE", number="INV-123")

    def test_tampered_reference_rejected(self):
        for kind, path in self.paths.items():
            with self.assertRaises(ValueError):
                self.render(kind, source=path.read_bytes() + b"tampered")

    def test_sources_and_snapshot_unchanged(self):
        before = deepcopy(self.snapshot)
        for kind, path in self.paths.items():
            digest = sha256(path.read_bytes()).digest()
            pdf = PdfReader(BytesIO(self.render(kind)), strict=True)
            self.assertEqual(len(pdf.pages), 1)
            self.assertFalse(pdf.get_fields())
            self.assertEqual(sha256(path.read_bytes()).digest(), digest)
        self.assertEqual(before, self.snapshot)
