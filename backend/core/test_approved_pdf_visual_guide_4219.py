"""Pure PDF guide-generation tests; no database required."""
import os
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_pdf_reference_integrity_4217 import APPROVED_PDFS
from .approved_pdf_visual_guide_4219 import build_visual_guide


class ApprovedPDFVisualGuideTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )

    def test_six_guides_preserve_page_counts(self):
        for kind, (_, _, expected_pages) in APPROVED_PDFS.items():
            with self.subTest(kind=kind):
                content = build_visual_guide(self.directory, kind)
                self.assertEqual(
                    len(PdfReader(BytesIO(content)).pages),
                    expected_pages,
                )

    def test_guides_are_not_original_files(self):
        for kind, (filename, _, _) in APPROVED_PDFS.items():
            with self.subTest(kind=kind):
                original = (self.directory / filename).read_bytes()
                guide = build_visual_guide(self.directory, kind)
                self.assertNotEqual(original, guide)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            build_visual_guide(self.directory, "UNKNOWN")

    def test_missing_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            build_visual_guide(
                self.directory / "DOES_NOT_EXIST_4219", "INVOICE"
            )