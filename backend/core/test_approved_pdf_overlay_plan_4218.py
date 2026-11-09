"""Read-only approved PDF placement inventory tests."""
import os
from pathlib import Path

from django.test import SimpleTestCase

from .approved_pdf_overlay_plan_4218 import (
    ANCHORS,
    build_placement_inventory,
)
from .approved_pdf_reference_integrity_4217 import APPROVED_PDFS


class ApprovedPDFOverlayPlanTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )

    def test_all_six_verified_documents_have_page_geometry(self):
        result = build_placement_inventory(self.directory)
        self.assertEqual(set(result), set(APPROVED_PDFS))
        for kind, details in result.items():
            with self.subTest(kind=kind):
                self.assertEqual(
                    len(details["pages"]), APPROVED_PDFS[kind][2]
                )
                for page in details["pages"]:
                    self.assertGreater(page["width_points"], 0)
                    self.assertGreater(page["height_points"], 0)

    def test_all_overlays_and_customer_release_remain_disabled(self):
        result = build_placement_inventory(self.directory)
        for details in result.values():
            self.assertFalse(details["overlay_authorized"])
            self.assertFalse(
                details["customer_document_release_authorized"]
            )
            for page in details["pages"]:
                self.assertEqual(
                    page["placement_status"],
                    "REQUIRES_VISUAL_REVIEW",
                )

    def test_label_candidates_are_document_specific(self):
        result = build_placement_inventory(self.directory)
        for kind, details in result.items():
            permitted = set(ANCHORS[kind])
            for page in details["pages"]:
                self.assertTrue(
                    set(page["candidate_labels"]).issubset(permitted)
                )

    def test_originals_are_not_modified_by_inspection(self):
        from hashlib import sha256
        before = {
            name: sha256((self.directory / name).read_bytes()).hexdigest()
            for name, _, _ in APPROVED_PDFS.values()
        }
        build_placement_inventory(self.directory)
        after = {
            name: sha256((self.directory / name).read_bytes()).hexdigest()
            for name, _, _ in APPROVED_PDFS.values()
        }
        self.assertEqual(before, after)