"""Alignment regression for both approved completion references."""
import os
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .approved_completion_previews_4227 import (
    POSITIONS, create_completion_preview,
)


class CompletionAlignment4229Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = Path(
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

    def render(self, kind):
        self.snapshot["financing_type"] = (
            "FINANCED" if kind == "COMPLETION_FINANCED"
            else "NON_FINANCED"
        )
        return create_completion_preview(
            self.reference, self.snapshot, "TEST-PROJECT-4229", kind
        )

    def test_non_financed_positions_match_printed_lines(self):
        self.assertEqual(
            POSITIONS["COMPLETION_NON_FINANCED"],
            {
                "customer_name": (113, 333, 106),
                "project_address": (76, 278, 146),
                "project_city": (265, 278, 117),
                "project_state": (431, 278, 26),
                "project_zip": (496, 278, 43),
                "project_code": (189, 234, 100),
            },
        )

    def test_financed_positions_match_printed_lines(self):
        self.assertEqual(
            POSITIONS["COMPLETION_FINANCED"],
            {
                "customer_name": (113, 136, 129),
                "project_address": (76, 103, 167),
                "project_city": (288, 103, 116),
                "project_state": (454, 103, 26),
                "project_zip": (519, 103, 43),
                "project_code": (189, 70, 100),
            },
        )

    def test_both_previews_contain_correct_customer_project(self):
        for kind in POSITIONS:
            with self.subTest(kind=kind):
                content = self.render(kind)
                reader = PdfReader(BytesIO(content), strict=True)
                self.assertEqual(len(reader.pages), 1)
                visible = reader.pages[0].extract_text()
                for expected in (
                    "FICTIONAL CUSTOMER",
                    "100 Example Street",
                    "Baltimore",
                    "21201",
                    "TEST-PROJECT-4229",
                    "WORK NOT VERIFIED",
                ):
                    self.assertIn(expected, visible)

    def test_financing_mismatch_still_fails_closed(self):
        with self.assertRaises(ValueError):
            create_completion_preview(
                self.reference, self.snapshot,
                "TEST-PROJECT-4229", "COMPLETION_FINANCED"
            )

    def test_originals_and_source_snapshot_remain_unchanged(self):
        original_snapshot = deepcopy(self.snapshot)
        paths = (
            "Completion Certificate ref1103NF.pdf",
            "Completion Certificate ref1103F.pdf",
        )
        before = {
            name: sha256((self.reference / name).read_bytes()).hexdigest()
            for name in paths
        }

        self.render("COMPLETION_NON_FINANCED")
        self.render("COMPLETION_FINANCED")
        self.snapshot = original_snapshot

        for name in paths:
            self.assertEqual(
                sha256((self.reference / name).read_bytes()).hexdigest(),
                before[name],
            )