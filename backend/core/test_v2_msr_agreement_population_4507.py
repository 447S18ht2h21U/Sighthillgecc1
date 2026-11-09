"""Isolated tests for MSR-driven fictional customer document population."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .v2_msr_agreement_population_4507 import fictional_document_preview


class MSRAgreement4507Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = Path(__file__).resolve().parents[2] / (
            "docs/reference/GECC-20261107-final-seven"
        )
        cls.files = {
            "CUSTOMER_SOW": "GECC Project Scope of Work 20261107v2.pdf",
            "AGREEMENT": "GECC Project SOW Agreement Maryland 20261107v2.pdf",
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
            "equipment": [],
        }

    def render(self, kind, source=None):
        original = (
            self.folder / self.files[kind]
        ).read_bytes() if source is None else source
        return fictional_document_preview(
            original, kind, self.snapshot, "TEST-001", "V1",
            "2026-11-08", "FICTIONAL SALES ASSOCIATE"
        )

    def test_sow_populates_customer_fields_on_first_page(self):
        pdf = PdfReader(BytesIO(self.render("CUSTOMER_SOW")), strict=True)
        self.assertEqual(len(pdf.pages), 2)
        text = pdf.pages[0].extract_text()
        for value in ("FICTIONAL AVERY SAMPLE", "555-0100",
                      "avery@example.invalid", "123 Fictional Lane",
                      "TEST-001", "FICTIONAL SALES ASSOCIATE"):
            self.assertIn(value, text)

    def test_agreement_populates_address_without_extra_page(self):
        pdf = PdfReader(BytesIO(self.render("AGREEMENT")), strict=True)
        self.assertEqual(len(pdf.pages), 3)
        text = pdf.pages[0].extract_text()
        for value in ("123 Fictional Lane", "Sample City", "MD", "00000"):
            self.assertIn(value, text)

    def test_agreement_later_pages_text_unchanged(self):
        original = PdfReader(self.folder / self.files["AGREEMENT"])
        preview = PdfReader(BytesIO(self.render("AGREEMENT")))
        for number in (1, 2):
            self.assertEqual(
                original.pages[number].extract_text(),
                preview.pages[number].extract_text()
            )

    def test_original_pdfs_unchanged(self):
        for kind, filename in self.files.items():
            path = self.folder / filename
            before = sha256(path.read_bytes()).hexdigest()
            self.render(kind)
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), before)

    def test_msr_snapshot_not_mutated(self):
        original = deepcopy(self.snapshot)
        self.render("CUSTOMER_SOW")
        self.render("AGREEMENT")
        self.assertEqual(self.snapshot, original)

    def test_nonfictional_customer_denied(self):
        self.snapshot["customer"] = "REAL CUSTOMER"
        for kind in self.files:
            with self.assertRaises(ValueError):
                self.render(kind)

    def test_tampered_reference_denied(self):
        for kind, filename in self.files.items():
            altered = (self.folder / filename).read_bytes() + b"tamper"
            with self.assertRaises(ValueError):
                self.render(kind, source=altered)

    def test_oversized_field_denied(self):
        self.snapshot["project_location"] = "X" * 200
        for kind in self.files:
            with self.assertRaises(ValueError):
                self.render(kind)
