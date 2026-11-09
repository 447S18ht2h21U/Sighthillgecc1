"""Fictional financing and completion-certificate selection safeguards."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .msr_commercial_page2_4510 import (
    fictional_commercial_sow_preview,
    completion_certificate_reference_kind,
)
from .v2_document_mapping_4489 import reference_details


class FinancingCertificate4511Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = (
            Path(__file__).resolve().parents[2]
            / "docs/reference/GECC-20261107-final-seven"
            / "GECC Project Scope of Work 20261107v2.pdf"
        )

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
            "scope": "Fictional equipment installation.",
            "financing_type": "NON_FINANCED",
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

    def preview_text(self):
        result = fictional_commercial_sow_preview(
            self.reference.read_bytes(), self.snapshot,
            "TEST-001", "V1", "2026-11-08",
            "FICTIONAL SALES ASSOCIATE",
        )
        pdf = PdfReader(BytesIO(result), strict=True)
        self.assertEqual(len(pdf.pages), 2)
        self.assertFalse(pdf.get_fields())
        return pdf.pages[1].extract_text()

    def test_nonfinanced_displays_no(self):
        self.assertIn("NO", self.preview_text())

    def test_financed_displays_yes(self):
        self.snapshot["financing_type"] = "FINANCED"
        self.assertIn("YES", self.preview_text())

    def test_nonfinanced_selects_nonfinanced_certificate(self):
        kind = completion_certificate_reference_kind(self.snapshot)
        self.assertEqual(kind, "COMPLETION_NON_FINANCED")
        self.assertEqual(reference_details(kind)["stage"], "POST_INSTALLATION")

    def test_financed_selects_financed_certificate(self):
        self.snapshot["financing_type"] = "FINANCED"
        kind = completion_certificate_reference_kind(self.snapshot)
        self.assertEqual(kind, "COMPLETION_FINANCED")
        self.assertEqual(reference_details(kind)["stage"], "POST_INSTALLATION")

    def test_unknown_financing_rejected(self):
        self.snapshot["financing_type"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            completion_certificate_reference_kind(self.snapshot)
        with self.assertRaises(ValueError):
            self.preview_text()

    def test_snapshot_not_modified(self):
        before = deepcopy(self.snapshot)
        completion_certificate_reference_kind(self.snapshot)
        self.preview_text()
        self.assertEqual(self.snapshot, before)
