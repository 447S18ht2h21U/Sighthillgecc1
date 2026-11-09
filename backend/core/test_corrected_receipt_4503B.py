"""Corrected survey Receipt selection regression."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .v2_document_mapping_4489 import reference_details, verify_reference
from .v2_pdf_overlay_4495 import fictional_preview


class CorrectedReceiptTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(__file__).resolve().parents[2]
        cls.corrected = cls.root / "docs/reference/GECC-20261107-v4-survey-corrected"
        cls.previous = cls.root / "docs/reference/GECC-20261107-final-seven/GECC Receipt 20261107v4.pdf"

    def test_corrected_receipt_is_selected(self):
        self.assertEqual(
            reference_details("RECEIPT")["filename"],
            "GECC Receipt 20261107v4-survey-corrected.pdf",
        )

    def test_corrected_receipt_verifies_and_is_one_page(self):
        details = verify_reference(
            "RECEIPT",
            self.root / "docs/reference/GECC-20261107-final-seven",
        )
        pdf = PdfReader(self.corrected / details["filename"], strict=True)
        self.assertEqual(len(pdf.pages), 1)

    def test_original_receipt_is_preserved(self):
        self.assertEqual(
            sha256(self.previous.read_bytes()).hexdigest().upper(),
            "8FD9A2B5C01E0DA2D0BC5D652C3F1B3BC4613EA62DED4CE4D7FC5C3D8C19A3A6",
        )

    def test_preview_never_manufactures_signatures(self):
        path = self.corrected / reference_details("RECEIPT")["filename"]
        before = path.read_bytes()
        result = fictional_preview(
            before, "RECEIPT", "FICTIONAL AVERY SAMPLE", "TEST-001"
        )
        self.assertEqual(path.read_bytes(), before)
        pdf = PdfReader(BytesIO(result), strict=True)
        self.assertEqual(len(pdf.pages), 1)
        self.assertFalse(pdf.get_fields())
