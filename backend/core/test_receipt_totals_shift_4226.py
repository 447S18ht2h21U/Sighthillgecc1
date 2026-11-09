"""Focused 12-point Receipt totals shift regression."""
import inspect
import os
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from . import approved_receipt_overlay_preview_4223 as renderer
from .test_receipt_alignment_4225 import ReceiptAlignment4225Tests


class ReceiptTotalsShift4226Tests(SimpleTestCase):
    def test_amount_values_are_shifted_left(self):
        source = inspect.getsource(renderer.create_receipt_preview)
        self.assertIn(
            "pen.drawRightString(746, y, value)", source
        )
        self.assertNotIn(
            "pen.drawRightString(758, y, value)", source
        )

    def test_existing_amount_background_is_preserved(self):
        source = inspect.getsource(renderer.create_receipt_preview)
        self.assertIn(
            "pen.rect(695, y - 3, 68, 13, stroke=0, fill=1)",
            source,
        )

    def test_corrected_preview_keeps_financial_values(self):
        fixture = ReceiptAlignment4225Tests()
        fixture.setUp()
        fixture.directory = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )
        content = fixture.render()
        reader = PdfReader(BytesIO(content), strict=True)
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        for value in ("10,000.00", "500.00", "10,500.00"):
            self.assertIn(value, text)
        self.assertIn("PAYMENT NOT VERIFIED", text)