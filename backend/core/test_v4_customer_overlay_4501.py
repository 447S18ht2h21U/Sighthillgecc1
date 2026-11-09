"""Isolated fictional expanded customer PDF regression."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .v4_customer_overlay_4501 import fictional_customer_preview


class ExpandedCustomerPDFTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        folder = Path(__file__).resolve().parents[2] / "docs/reference/GECC-20261107-final-seven"
        cls.paths = {
            "INVOICE": folder / "GECC Invoice 20261107v4.pdf",
            "RECEIPT": folder.parent / "GECC-20261107-v4-survey-corrected" / "GECC Receipt 20261107v4-survey-corrected.pdf",
        }

    def setUp(self):
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

    def render(self, kind, fields=None):
        return fictional_customer_preview(
            self.paths[kind].read_bytes(),
            kind,
            self.fields if fields is None else fields,
        )

    def test_all_eight_values_appear_in_both_pdfs(self):
        for kind in self.paths:
            text = PdfReader(BytesIO(self.render(kind))).pages[0].extract_text()
            for value in self.fields.values():
                with self.subTest(kind=kind, value=value):
                    self.assertIn(value, text)

    def test_both_pdfs_are_one_page(self):
        for kind in self.paths:
            self.assertEqual(len(PdfReader(BytesIO(self.render(kind))).pages), 1)

    def test_reference_bytes_unchanged(self):
        for kind, path in self.paths.items():
            before = path.read_bytes()
            self.render(kind)
            self.assertEqual(path.read_bytes(), before)

    def test_source_fields_unchanged(self):
        before = deepcopy(self.fields)
        self.render("INVOICE")
        self.assertEqual(self.fields, before)

    def test_long_address_rejected(self):
        with self.assertRaises(ValueError):
            self.render("INVOICE", dict(self.fields, project_address="X" * 100))

    def test_long_email_rejected(self):
        with self.assertRaises(ValueError):
            self.render("RECEIPT", dict(self.fields, customer_email="X" * 100))

    def test_missing_field_rejected(self):
        fields = dict(self.fields)
        del fields["project_zip"]
        with self.assertRaises(ValueError):
            self.render("INVOICE", fields)

    def test_extra_field_rejected(self):
        with self.assertRaises(ValueError):
            self.render("INVOICE", dict(self.fields, signature_verified=True))

    def test_real_customer_rejected(self):
        with self.assertRaises(ValueError):
            self.render("RECEIPT", dict(self.fields, customer_name="Actual Customer"))

    def test_tampered_reference_rejected(self):
        with self.assertRaises(ValueError):
            fictional_customer_preview(
                self.paths["INVOICE"].read_bytes() + b"tampered",
                "INVOICE", self.fields,
            )

    def test_unknown_document_rejected(self):
        with self.assertRaises(ValueError):
            fictional_customer_preview(b"", "AGREEMENT", self.fields)

    def test_no_signature_fields_manufactured(self):
        for kind in self.paths:
            self.assertFalse(PdfReader(BytesIO(self.render(kind))).get_fields())
