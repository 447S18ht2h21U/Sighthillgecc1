"""Focused financed/non-financed completion preview tests."""
import os
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_completion_previews_4227 import (
    create_completion_preview,
)


class ApprovedCompletionPreviews4227Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )

    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL CUSTOMER",
            "billing_address": "100 Example Street",
            "project_location": "100 Example Street",
            "project_city": "Baltimore",
            "project_state": "MD",
            "project_zip": "21201",
            "customer_phone": "555-0100",
            "customer_email": "sample@example.com",
            "equipment": [],
            "financing_type": "NON_FINANCED",
        }

    def render(self, kind="COMPLETION_NON_FINANCED"):
        return create_completion_preview(
            self.directory, self.snapshot, "TEST-PROJECT-4227", kind
        )

    def test_non_financed_preview(self):
        reader = PdfReader(BytesIO(self.render()))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn("FICTIONAL CUSTOMER", text)
        self.assertIn("TEST-PROJECT-4227", text)
        self.assertIn("WORK NOT VERIFIED", text)

    def test_financed_preview(self):
        self.snapshot["financing_type"] = "FINANCED"
        reader = PdfReader(
            BytesIO(self.render("COMPLETION_FINANCED"))
        )
        self.assertEqual(len(reader.pages), 1)
        self.assertIn(
            "FICTIONAL CUSTOMER", reader.pages[0].extract_text()
        )

    def test_financing_mismatch_rejected_both_ways(self):
        with self.assertRaises(ValueError):
            self.render("COMPLETION_FINANCED")
        self.snapshot["financing_type"] = "FINANCED"
        with self.assertRaises(ValueError):
            self.render("COMPLETION_NON_FINANCED")

    def test_missing_financing_rejected(self):
        self.snapshot.pop("financing_type")
        with self.assertRaises(ValueError):
            self.render()

    def test_no_completion_or_funding_assertion_added(self):
        for financing, kind in (
            ("NON_FINANCED", "COMPLETION_NON_FINANCED"),
            ("FINANCED", "COMPLETION_FINANCED"),
        ):
            self.snapshot["financing_type"] = financing
            result = self.render(kind)
            text = PdfReader(BytesIO(result)).pages[0].extract_text()
            self.assertIn("DO NOT SIGN OR SEND", text)
            self.assertNotIn("VERIDIAN COMPLETION VERIFIED", text)
            self.assertNotIn("VERIDIAN FUNDING AUTHORIZED", text)

    def test_missing_customer_rejected(self):
        self.snapshot["customer"] = ""
        with self.assertRaises(ValueError):
            self.render()

    def test_unsupported_character_rejected(self):
        self.snapshot["customer"] = "Sample \u2603"
        with self.assertRaises(ValueError):
            self.render()

    def test_snapshot_and_approved_originals_unchanged(self):
        original_snapshot = deepcopy(self.snapshot)
        names = (
            "Completion Certificate ref1103NF.pdf",
            "Completion Certificate ref1103F.pdf",
        )
        before = {
            name: sha256((self.directory / name).read_bytes()).hexdigest()
            for name in names
        }

        self.render()
        self.snapshot["financing_type"] = "FINANCED"
        self.render("COMPLETION_FINANCED")

        self.snapshot["financing_type"] = "NON_FINANCED"
        self.assertEqual(self.snapshot, original_snapshot)

        for name in names:
            self.assertEqual(
                before[name],
                sha256((self.directory / name).read_bytes()).hexdigest()
            )