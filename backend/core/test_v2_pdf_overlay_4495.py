"""Regression tests for strictly fictional Invoice/Receipt overlays."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .v2_pdf_overlay_4495 import CONFIG, fictional_preview


class V2PDFOverlayTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(__file__).resolve().parents[2]
        cls.paths = {
            "INVOICE": cls.root / "docs/reference/GECC-20261107-final-seven/GECC Invoice 20261107v4.pdf",
            "RECEIPT": cls.root / "docs/reference/GECC-20261107-v4-survey-corrected/GECC Receipt 20261107v4-survey-corrected.pdf",
        }

    def render(self, kind, customer="FICTIONAL AVERY SAMPLE", code="TEST-001"):
        return fictional_preview(
            self.paths[kind].read_bytes(), kind, customer, code
        )

    def test_both_documents_populate_customer_name(self):
        for kind in CONFIG:
            self.assertIn(
                "FICTIONAL AVERY SAMPLE",
                PdfReader(BytesIO(self.render(kind))).pages[0].extract_text(),
            )

    def test_both_documents_populate_same_project_code(self):
        for kind in CONFIG:
            self.assertIn(
                "TEST-001",
                PdfReader(BytesIO(self.render(kind))).pages[0].extract_text(),
            )

    def test_both_documents_remain_one_page(self):
        for kind in CONFIG:
            self.assertEqual(len(PdfReader(BytesIO(self.render(kind))).pages), 1)

    def test_original_references_remain_unchanged(self):
        for kind, path in self.paths.items():
            original = path.read_bytes()
            self.render(kind)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(
                sha256(original).hexdigest().upper(),
                CONFIG[kind]["sha256"],
            )

    def test_real_customer_rejected(self):
        with self.assertRaises(ValueError):
            self.render("INVOICE", customer="Actual Customer")

    def test_overlong_field_rejected(self):
        with self.assertRaises(ValueError):
            self.render("RECEIPT", customer="FICTIONAL " + "X" * 100)

    def test_unsupported_kind_rejected(self):
        with self.assertRaises(ValueError):
            fictional_preview(b"PDF", "AGREEMENT", "FICTIONAL X", "P1")

    def test_changed_reference_rejected(self):
        original = self.paths["INVOICE"].read_bytes()
        with self.assertRaises(ValueError):
            fictional_preview(
                original + b"tampered", "INVOICE", "FICTIONAL X", "P1"
            )

    def test_blank_project_code_rejected(self):
        with self.assertRaises(ValueError):
            self.render("INVOICE", code="")

    def test_no_original_annotation_changes(self):
        for kind in CONFIG:
            reader = PdfReader(BytesIO(self.render(kind)))
            self.assertFalse(reader.get_fields())