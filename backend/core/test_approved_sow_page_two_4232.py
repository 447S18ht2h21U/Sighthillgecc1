"""Focused page-two integration tests; no persistent database."""
import os
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_sow_page_two_4232 import (
    create_page_two_sow_preview,
)
from .test_approved_sow_commercial_4231 import SOWCommercial4231Tests


class SOWPageTwo4232Tests(SimpleTestCase):
    def setUp(self):
        fixture = SOWCommercial4231Tests()
        fixture.setUp()
        self.snapshot = deepcopy(fixture.snapshot)
        self.reference = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )
        self.snapshot["installation_details"] = "Test system operation."
        self.snapshot["additional_project_notes"] = "Fictional preview."
        self.snapshot["payment_terms"] = "Approved fictional payment schedule."

    def render(self):
        return create_page_two_sow_preview(
            self.reference, self.snapshot, "TEST-PROJECT-4232",
            "4232-1", "2026-11-04", "FICTIONAL ASSOCIATE"
        )

    def test_commercial_values_appear_on_actual_page_two(self):
        pages = PdfReader(BytesIO(self.render()), strict=True).pages
        self.assertEqual(len(pages), 3)
        text = pages[1].extract_text()
        for amount in ("10,000.00", "-150.00", "10,350.00"):
            self.assertIn(amount, text)

    def test_scope_financing_and_promotion_are_on_page_two(self):
        text = PdfReader(BytesIO(self.render())).pages[1].extract_text()
        for value in (
            "Install the fictional heat pump",
            "Reduced Price",
            "Non-Financed",
            "Approved fictional payment schedule",
        ):
            self.assertIn(value, text)

    def test_source_snapshot_not_changed(self):
        original = deepcopy(self.snapshot)
        self.render()
        self.assertEqual(self.snapshot, original)

    def test_wrong_total_is_rejected(self):
        self.snapshot["total_price"] = "9999.00"
        with self.assertRaises(ValueError):
            self.render()

    def test_long_scope_retained_in_appendix(self):
        self.snapshot["scope"] = "Install fictional equipment. " * 20
        content = self.render()
        pages = PdfReader(BytesIO(content)).pages
        self.assertIn(
            "See development detail appendix",
            pages[1].extract_text(),
        )
        self.assertIn(
            "Install fictional equipment.",
            pages[2].extract_text(),
        )