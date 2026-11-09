"""Targeted development tests for approved SOW and Agreement previews."""
import os
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_sow_agreement_previews_4230 import (
    create_sow_preview, create_agreement_preview
)


class SOWAgreement4230Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = Path(os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"])

    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL CUSTOMER",
            "billing_address": "100 Example Road",
            "project_location": "100 Example Road",
            "project_city": "Baltimore",
            "project_state": "MD",
            "project_zip": "21201",
            "customer_phone": "555-0100",
            "customer_email": "sample@example.com",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "TEST-HP-100",
                "description": "Fictional equipment",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
        }

    def sow(self):
        return create_sow_preview(
            self.directory, self.snapshot, "TEST-PROJECT-4230",
            "4230-1", "2026-11-04", "FICTIONAL ASSOCIATE"
        )

    def agreement(self):
        return create_agreement_preview(
            self.directory, self.snapshot, "TEST-PROJECT-4230", "4230-1"
        )

    def test_sow_has_original_two_pages_and_equipment(self):
        pdf = PdfReader(BytesIO(self.sow()))
        self.assertEqual(len(pdf.pages), 2)
        text = pdf.pages[0].extract_text()
        for item in ("FICTIONAL CUSTOMER", "TEST-HP-100",
                     "TEST-PROJECT-4230", "FICTIONAL SOW PREVIEW"):
            self.assertIn(item, text)

    def test_agreement_preserves_three_pages_and_adds_review_sheet(self):
        pdf = PdfReader(BytesIO(self.agreement()))
        self.assertEqual(len(pdf.pages), 4)
        text = pdf.pages[3].extract_text()
        for item in ("FICTIONAL CUSTOMER", "TEST-PROJECT-4230",
                     "NOT PART OF SIGNED AGREEMENT"):
            self.assertIn(item, text)

    def test_msr_customer_consistent_between_both(self):
        self.assertIn("FICTIONAL CUSTOMER",
                      PdfReader(BytesIO(self.sow())).pages[0].extract_text())
        self.assertIn("FICTIONAL CUSTOMER",
                      PdfReader(BytesIO(self.agreement())).pages[3].extract_text())

    def test_missing_customer_denied_for_both(self):
        self.snapshot["customer"] = ""
        for build in (self.sow, self.agreement):
            with self.assertRaises(ValueError):
                build()

    def test_invalid_equipment_denied_for_sow(self):
        self.snapshot["equipment"][0]["category_of_work"] = "Invalid"
        with self.assertRaises(ValueError):
            self.sow()

    def test_originals_and_snapshot_unchanged(self):
        old = deepcopy(self.snapshot)
        names = ("GECC Project Scope of Work ref1103a.pdf",
                 "GECC Project  Agreement ref1103MD.pdf")
        before = {name: sha256((self.directory / name).read_bytes()).hexdigest()
                  for name in names}
        self.sow()
        self.agreement()
        self.assertEqual(self.snapshot, old)
        for name in names:
            self.assertEqual(
                sha256((self.directory / name).read_bytes()).hexdigest(),
                before[name]
            )