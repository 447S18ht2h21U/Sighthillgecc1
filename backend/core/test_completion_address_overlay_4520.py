"""Isolated Completion Certificate address regression."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .completion_address_overlay_4520 import (
    fictional_complete_certificate_address,
)


class CompletionAddress4520Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(__file__).resolve().parents[2]
        folder = root / "docs/reference/GECC-20261107-final-seven"
        cls.paths = {
            "COMPLETION_FINANCED":
                folder / "GECC FINANCED Completion Certificate 20261107v2.pdf",
            "COMPLETION_NON_FINANCED":
                folder / "GECC NOT-FINANCED Completion Certificate 20261107v2.pdf",
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
                "notes": "Fictional retail discount",
            },
        }

    def render(self, kind, source=None):
        self.snapshot["financing_type"] = (
            "FINANCED" if kind == "COMPLETION_FINANCED"
            else "NON_FINANCED"
        )
        return fictional_complete_certificate_address(
            self.paths[kind].read_bytes() if source is None else source,
            kind, self.snapshot, "TEST-001", "V1"
        )

    def test_both_certificates_have_complete_address(self):
        for kind in self.paths:
            with self.subTest(kind=kind):
                pdf = PdfReader(BytesIO(self.render(kind)), strict=True)
                text = pdf.pages[0].extract_text()
                for value in ("FICTIONAL AVERY SAMPLE",
                              "123 Fictional Lane", "Sample City",
                              "MD", "00000", "TEST-001"):
                    self.assertIn(value, text)

    def test_both_certificates_are_one_page(self):
        for kind in self.paths:
            pdf = PdfReader(BytesIO(self.render(kind)), strict=True)
            self.assertEqual(len(pdf.pages), 1)
            self.assertFalse(pdf.get_fields())

    def test_missing_state_rejected(self):
        self.snapshot["project_state"] = ""
        with self.assertRaises(ValueError):
            self.render("COMPLETION_FINANCED")

    def test_invalid_zip_rejected(self):
        self.snapshot["project_zip"] = "ABCDE"
        with self.assertRaises(ValueError):
            self.render("COMPLETION_NON_FINANCED")

    def test_oversized_city_rejected(self):
        self.snapshot["project_city"] = "Extremely Long Fictional City Name"
        with self.assertRaises(ValueError):
            self.render("COMPLETION_FINANCED")

    def test_tampered_pdf_rejected(self):
        for kind, path in self.paths.items():
            with self.assertRaises(ValueError):
                self.render(kind, path.read_bytes() + b"tampered")

    def test_originals_and_snapshot_preserved(self):
        for kind, path in self.paths.items():
            before_pdf = sha256(path.read_bytes()).digest()
            self.snapshot["financing_type"] = (
                "FINANCED" if kind == "COMPLETION_FINANCED"
                else "NON_FINANCED"
            )
            before_snapshot = deepcopy(self.snapshot)
            self.render(kind)
            self.assertEqual(before_pdf, sha256(path.read_bytes()).digest())
            self.assertEqual(before_snapshot, self.snapshot)
