"""Regression safeguards for the seven current customer-facing PDFs."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .v2_document_mapping_4489 import REFERENCE_FILES, verify_reference
from .v2_pdf_overlay_4495 import fictional_preview


class FinalSevenMappingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(__file__).resolve().parents[2]
        cls.current = cls.root / "docs/reference/GECC-20261107-final-seven"

    def test_all_seven_resolve_to_final_directory(self):
        self.assertEqual(len(REFERENCE_FILES), 7)
        for kind in REFERENCE_FILES:
            with self.subTest(kind=kind):
                self.assertEqual(verify_reference(kind, self.current)["kind"], kind)

    def test_invoice_and_receipt_are_v4(self):
        self.assertEqual(
            REFERENCE_FILES["INVOICE"][0], "GECC Invoice 20261107v4.pdf"
        )
        self.assertEqual(
            REFERENCE_FILES["RECEIPT"][0], "GECC Receipt 20261107v4-survey-corrected.pdf"
        )

    def test_old_invoice_and_receipt_not_selected(self):
        self.assertNotIn(
            REFERENCE_FILES["INVOICE"][0],
            {"GECC Invoice 20261107v2.pdf", "GECC Invoice 20261107v3.pdf"},
        )
        self.assertNotIn(
            REFERENCE_FILES["RECEIPT"][0],
            {"GECC Receipt 20261107v2.pdf", "GECC Receipt 20261107v3.pdf"},
        )

    def test_fictional_previews_preserve_v4_originals(self):
        for kind in ("INVOICE", "RECEIPT"):
            name, fingerprint = REFERENCE_FILES[kind]
            path = (
                self.current.parent / "GECC-20261107-v4-survey-corrected" / name
                if kind == "RECEIPT" else self.current / name
            )
            original = path.read_bytes()
            result = fictional_preview(
                original, kind, "FICTIONAL AVERY SAMPLE", "TEST-001"
            )
            self.assertEqual(
                sha256(path.read_bytes()).hexdigest().upper(), fingerprint
            )
            self.assertEqual(path.read_bytes(), original)
            pdf = PdfReader(BytesIO(result), strict=True)
            self.assertEqual(len(pdf.pages), 1)
            extracted = pdf.pages[0].extract_text() or ""
            self.assertIn("FICTIONAL AVERY SAMPLE", extracted)
            self.assertIn("TEST-001", extracted)
