"""Approved-reference file integrity tests. No database connections."""
import os
from pathlib import Path

from django.test import SimpleTestCase

from .approved_document_mapping_4215 import APPROVED_REFERENCE_FILES
from .approved_pdf_reference_integrity_4217 import (
    APPROVED_PDFS,
    verify_all_references,
    verify_reference,
)


class ApprovedPDFReferenceIntegrityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = Path(os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"])

    def test_all_six_originals_match_approved_fingerprints(self):
        result = verify_all_references(self.directory)
        self.assertEqual(len(result), 6)
        for kind, reference in result.items():
            with self.subTest(kind=kind):
                self.assertEqual(reference.kind, kind)
                self.assertEqual(len(reference.sha256), 64)

    def test_reference_names_match_msr_mapping(self):
        self.assertEqual(set(APPROVED_REFERENCE_FILES), set(APPROVED_PDFS))
        for kind, filename in APPROVED_REFERENCE_FILES.items():
            with self.subTest(kind=kind):
                self.assertEqual(filename, APPROVED_PDFS[kind][0])

    def test_unknown_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_reference(self.directory, "UNAPPROVED")

    def test_missing_reference_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_all_references(
                self.directory / "DOES_NOT_EXIST_4217"
            )