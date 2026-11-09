"""Pure approved-reference projection checks; no database required."""
from copy import deepcopy
from django.test import SimpleTestCase

from .approved_document_mapping_4215 import (
    APPROVED_REFERENCE_FILES,
    approved_reference_filename,
    project_document_projection,
)


class ApprovedDocumentMappingTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = {
            "customer": "Sample Customer",
            "billing_address": "Billing Street",
            "project_location": "Installation Street",
            "project_city": "Baltimore",
            "project_state": "MD",
            "project_zip": "21201",
            "customer_phone": "555-0101",
            "customer_email": "sample@example.com",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pump",
                "model_number": "EXAMPLE-100",
                "description": "Fictional test unit",
                "quantity": 1,
                "category_of_work": "New installation",
            }],
        }

    def test_all_six_approved_references_are_recognized(self):
        self.assertEqual(len(APPROVED_REFERENCE_FILES), 6)
        for kind, filename in APPROVED_REFERENCE_FILES.items():
            with self.subTest(kind=kind):
                self.assertEqual(
                    approved_reference_filename(kind), filename
                )

    def test_customer_name_consistent_across_all_six(self):
        for kind in APPROVED_REFERENCE_FILES:
            with self.subTest(kind=kind):
                values = project_document_projection(
                    self.snapshot, kind
                )
                self.assertEqual(
                    values["customer_name"], "Sample Customer"
                )

    def test_contact_and_address_follow_msr(self):
        for kind in APPROVED_REFERENCE_FILES:
            with self.subTest(kind=kind):
                values = project_document_projection(
                    self.snapshot, kind
                )
                self.assertEqual(
                    values["customer_email"], "sample@example.com"
                )
                self.assertEqual(
                    values["project_address"], "Installation Street"
                )
                self.assertEqual(values["project_state"], "MD")

    def test_equipment_documents_receive_eight_rows(self):
        for kind in ("CUSTOMER_SOW", "INVOICE", "RECEIPT"):
            with self.subTest(kind=kind):
                rows = project_document_projection(
                    self.snapshot, kind
                )["equipment_rows"]
                self.assertEqual(len(rows), 8)
                self.assertEqual(rows[0]["brand"], "Goodman")
                self.assertEqual(
                    rows[0]["category"], "New installation"
                )
                self.assertEqual(rows[0]["serial_number"], "")
                self.assertEqual(rows[0]["price"], "")

    def test_no_installation_evidence_is_invented(self):
        for kind in APPROVED_REFERENCE_FILES:
            values = project_document_projection(
                self.snapshot, kind
            )
            self.assertNotIn("signature", values)
            self.assertNotIn("delivery_verified", values)
            self.assertNotIn("payment_verified", values)

    def test_projection_does_not_mutate_approved_snapshot(self):
        original = deepcopy(self.snapshot)
        projected = project_document_projection(
            self.snapshot, "INVOICE"
        )
        projected["equipment_rows"][0]["brand"] = "Changed"
        self.assertEqual(self.snapshot, original)

    def test_unknown_document_type_is_rejected(self):
        with self.assertRaises(ValueError):
            project_document_projection(self.snapshot, "UNKNOWN")

    def test_missing_customer_is_rejected(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["customer"] = ""
        with self.assertRaises(ValueError):
            project_document_projection(snapshot, "AGREEMENT")

    def test_invalid_equipment_is_rejected(self):
        snapshot = deepcopy(self.snapshot)
        snapshot["equipment"][0]["category_of_work"] = "Invented"
        with self.assertRaises(ValueError):
            project_document_projection(snapshot, "INVOICE")

    def test_document_projection_never_claims_delivery(self):
        values = project_document_projection(
            self.snapshot, "RECEIPT"
        )
        self.assertNotIn("email_sent", values)
        self.assertNotIn("receipt_paid", values)
        self.assertNotIn("completion_authorized", values)