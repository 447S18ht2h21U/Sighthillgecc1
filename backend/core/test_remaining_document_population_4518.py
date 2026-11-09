"""Isolated tests for remaining fictional document population."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .remaining_document_population_4518 import (
    fictional_remaining_document,
)


class RemainingDocuments4518Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(__file__).resolve().parents[2]
        folder = root / "docs/reference/GECC-20261107-final-seven"

        cls.paths = {
            "EXPEDITED_SERVICE":
                folder / "GECC Expedite Service Request 20261107v2.pdf",
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
        if kind == "COMPLETION_NON_FINANCED":
            self.snapshot["financing_type"] = "NON_FINANCED"
        elif kind == "COMPLETION_FINANCED":
            self.snapshot["financing_type"] = "FINANCED"

        return fictional_remaining_document(
            self.paths[kind].read_bytes() if source is None else source,
            kind, self.snapshot, "TEST-001", "V1",
        )

    def test_all_three_documents_receive_customer_details(self):
        for kind in self.paths:
            pdf = PdfReader(BytesIO(self.render(kind)), strict=True)
            self.assertEqual(len(pdf.pages), 1)
            text = pdf.pages[0].extract_text() or ""
            for value in ("FICTIONAL AVERY SAMPLE", "123 Fictional Lane",
                          "TEST-001"):
                self.assertIn(value, text)

    def test_financed_certificate_selected_correctly(self):
        pdf = PdfReader(
            BytesIO(self.render("COMPLETION_FINANCED")), strict=True
        )
        self.assertIn(
            "financing application",
            pdf.pages[0].extract_text(),
        )

    def test_nonfinanced_certificate_selected_correctly(self):
        pdf = PdfReader(
            BytesIO(self.render("COMPLETION_NON_FINANCED")), strict=True
        )
        self.assertIn(
            "does not request funding",
            pdf.pages[0].extract_text(),
        )

    def test_wrong_certificate_classification_rejected(self):
        self.snapshot["financing_type"] = "NON_FINANCED"
        with self.assertRaises(ValueError):
            fictional_remaining_document(
                self.paths["COMPLETION_FINANCED"].read_bytes(),
                "COMPLETION_FINANCED",
                self.snapshot,
                "TEST-001",
                "V1",
            )

    def test_unknown_financing_rejected(self):
        self.snapshot["financing_type"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            fictional_remaining_document(
                self.paths["COMPLETION_FINANCED"].read_bytes(),
                "COMPLETION_FINANCED",
                self.snapshot,
                "TEST-001",
                "V1",
            )

    def test_real_customer_preview_rejected(self):
        self.snapshot["customer"] = "REAL CUSTOMER"
        with self.assertRaises(ValueError):
            self.render("EXPEDITED_SERVICE")

    def test_tampered_references_rejected(self):
        for kind, path in self.paths.items():
            with self.assertRaises(ValueError):
                self.render(kind, path.read_bytes() + b"tampered")

    def test_originals_preserved(self):
        for kind, path in self.paths.items():
            before = sha256(path.read_bytes()).digest()
            self.render(kind)
            self.assertEqual(
                before,
                sha256(path.read_bytes()).digest(),
            )

    def test_no_signing_fields_or_authorizations_created(self):
        for kind in self.paths:
            pdf = PdfReader(BytesIO(self.render(kind)), strict=True)
            self.assertFalse(pdf.get_fields())
            text = pdf.pages[0].extract_text() or ""
            self.assertIn("Customer Signature:", text)
            self.assertIn("NOT SIGNED OR AUTHORIZED", text)

    def test_snapshot_not_modified_for_expedit(self):
        before = deepcopy(self.snapshot)
        self.render("EXPEDITED_SERVICE")
        self.assertEqual(before, self.snapshot)
