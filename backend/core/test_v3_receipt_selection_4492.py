"""Regression guards for current one-page V3 Receipt selection."""
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .v2_document_mapping_4489 import (
    REFERENCE_FILES,
    DOCUMENT_STAGES,
    reference_details,
    verify_reference,
    project_document_projection_v2,
)


class V3ReceiptSelectionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(__file__).resolve().parents[2]
        cls.v2 = cls.root / "docs/reference/GECC-20261107-v2"
        cls.v3 = cls.root / "docs/reference/GECC-20261107-final-seven"

    def test_current_receipt_is_v3(self):
        details = reference_details("RECEIPT")
        self.assertEqual(
            details["filename"],
            "GECC Receipt 20261107v4-survey-corrected.pdf",
        )
        self.assertEqual(
            details["sha256"],
            "02F94BA72A5FAE593278A2C781659FC97B0001A692216C8780D066C38155E300",
        )

    def test_current_receipt_has_exactly_one_page(self):
        path = self.v3.parent / "GECC-20261107-v4-survey-corrected" / reference_details("RECEIPT")["filename"]
        reader = PdfReader(path, strict=True)
        self.assertEqual(len(reader.pages), 1)
        self.assertGreater(
            float(reader.pages[0].mediabox.width),
            float(reader.pages[0].mediabox.height),
        )

    def test_legacy_receipt_remains_preserved(self):
        path = self.v2 / "GECC Receipt 20261107v2.pdf"
        self.assertTrue(path.is_file())
        self.assertEqual(len(PdfReader(path, strict=True).pages), 2)

    def test_all_seven_current_references_verify(self):
        self.assertEqual(len(REFERENCE_FILES), 7)
        for kind in REFERENCE_FILES:
            with self.subTest(kind=kind):
                details = verify_reference(kind, self.v3)
                self.assertEqual(details["kind"], kind)

    def test_receipt_keeps_post_installation_stage(self):
        self.assertEqual(
            DOCUMENT_STAGES["RECEIPT"],
            "POST_INSTALLATION",
        )

    def test_receipt_cannot_authorize_sending(self):
        snapshot = {
            "customer": "FICTIONAL Customer",
            "billing_address": "",
            "project_location": "Example Street",
            "project_city": "Example City",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "",
            "customer_email": "fictional@example.invalid",
            "equipment": [],
        }
        result = project_document_projection_v2(
            snapshot, "RECEIPT", "TEST-001", "1.0"
        )
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["legally_eligible_for_installation"])