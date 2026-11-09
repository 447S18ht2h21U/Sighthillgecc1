"""Regression for seven-document MSR shared-data contracts."""
from copy import deepcopy

from django.test import SimpleTestCase

from .v2_document_mapping_4489 import REFERENCE_FILES
from .v2_document_fields_4493 import (
    DOCUMENT_FIELDS,
    SEPARATE_STAGE_DATA,
    prepare_field_contract,
)


class V2DocumentFieldContractTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL Customer",
            "billing_address": "Billing Address",
            "project_location": "Installation Address",
            "project_city": "Fictional City",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "555-0100",
            "customer_email": "fictional@example.invalid",
            "equipment": [],
        }

    def project(self, kind):
        return prepare_field_contract(
            self.snapshot, kind, "TEST-001", "1.0"
        )

    def test_exactly_seven_document_contracts(self):
        self.assertEqual(set(DOCUMENT_FIELDS), set(REFERENCE_FILES))
        self.assertEqual(set(SEPARATE_STAGE_DATA), set(REFERENCE_FILES))

    def test_customer_identity_consistent(self):
        for kind in REFERENCE_FILES:
            with self.subTest(kind=kind):
                fields = self.project(kind)["shared_fields"]
                self.assertEqual(fields["customer_name"], "FICTIONAL Customer")
                self.assertEqual(fields["project_code"], "TEST-001")

    def test_installation_address_consistent_where_used(self):
        for kind in REFERENCE_FILES:
            fields = self.project(kind)["shared_fields"]
            self.assertEqual(
                fields["project_address"], "Installation Address"
            )

    def test_contact_details_on_customer_sow_invoice_receipt(self):
        for kind in ("CUSTOMER_SOW", "INVOICE", "RECEIPT"):
            fields = self.project(kind)["shared_fields"]
            self.assertEqual(
                fields["customer_email"], "fictional@example.invalid"
            )
            self.assertEqual(fields["customer_phone"], "555-0100")

    def test_sow_contains_contact_and_address(self):
        fields = self.project("CUSTOMER_SOW")["shared_fields"]
        self.assertEqual(fields["project_city"], "Fictional City")
        self.assertEqual(fields["project_state"], "MD")
        self.assertEqual(fields["project_zip"], "00000")

    def test_expediting_is_conditional(self):
        result = self.project("EXPEDITED_SERVICE")
        self.assertEqual(result["stage"], "CONDITIONAL_PREINSTALLATION")
        self.assertIn(
            "legal_eligibility_verification",
            result["separate_stage_data_required"],
        )

    def test_receipt_uses_v3(self):
        result = self.project("RECEIPT")
        self.assertEqual(
            result["reference"]["filename"],
            "GECC Receipt 20261107v4-survey-corrected.pdf",
        )

    def test_actual_serial_numbers_are_separate(self):
        result = self.project("RECEIPT")
        self.assertIn(
            "actual_equipment_serial_numbers",
            result["separate_stage_data_required"],
        )
        self.assertNotIn(
            "actual_equipment_serial_numbers",
            result["shared_fields"],
        )

    def test_financed_completion_is_distinct(self):
        financed = self.project("COMPLETION_FINANCED")
        other = self.project("COMPLETION_NON_FINANCED")
        self.assertNotEqual(
            financed["reference"]["filename"],
            other["reference"]["filename"],
        )

    def test_no_document_is_send_authorized(self):
        for kind in REFERENCE_FILES:
            result = self.project(kind)
            self.assertFalse(result["send_authorized"])
            self.assertFalse(result["signature_verified"])
            self.assertFalse(result["installation_eligible"])
            self.assertFalse(result["completion_verified"])
            self.assertFalse(result["payment_verified"])

    def test_source_snapshot_unchanged(self):
        original = deepcopy(self.snapshot)
        for kind in REFERENCE_FILES:
            self.project(kind)
        self.assertEqual(self.snapshot, original)

    def test_unknown_document_denied(self):
        with self.assertRaises(ValueError):
            self.project("UNSUPPORTED")

    def test_missing_customer_denied(self):
        self.snapshot["customer"] = ""
        with self.assertRaises(ValueError):
            self.project("AGREEMENT")