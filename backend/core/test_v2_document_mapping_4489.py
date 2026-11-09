"""Isolated V2 reference and shared-field regression tests."""
from copy import deepcopy
from pathlib import Path

from django.test import SimpleTestCase

from .v2_document_mapping_4489 import (
    REFERENCE_FILES, DOCUMENT_STAGES, reference_details,
    verify_reference, project_document_projection_v2,
)


class V2DocumentMappingTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL Customer",
            "billing_address": "Billing Street",
            "project_location": "Installation Street",
            "project_city": "Test City",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "555-0100",
            "customer_email": "fictional@example.invalid",
            "equipment": [],
        }

    def test_seven_exact_document_kinds(self):
        self.assertEqual(len(REFERENCE_FILES), 7)

    def test_seven_stage_assignments(self):
        self.assertEqual(set(DOCUMENT_STAGES), set(REFERENCE_FILES))

    def test_unknown_kind_denied(self):
        with self.assertRaises(ValueError):
            reference_details("UNKNOWN")

    def test_all_reference_hashes_are_valid(self):
        directory = (
            Path(__file__).resolve().parents[2]
            / "docs/reference/GECC-20261107-final-seven"
        )
        for kind in REFERENCE_FILES:
            with self.subTest(kind=kind):
                self.assertEqual(verify_reference(kind, directory)["kind"], kind)

    def test_customer_name_consistent_across_seven_documents(self):
        for kind in REFERENCE_FILES:
            with self.subTest(kind=kind):
                result = project_document_projection_v2(
                    self.snapshot, kind, "PROJECT-001", "1.0"
                )
                self.assertEqual(result["customer_name"], "FICTIONAL Customer")

    def test_address_and_contact_consistency(self):
        for kind in REFERENCE_FILES:
            result = project_document_projection_v2(
                self.snapshot, kind, "PROJECT-001", "1.0"
            )
            self.assertEqual(result["project_address"], "Installation Street")
            self.assertEqual(result["customer_email"], "fictional@example.invalid")

    def test_missing_customer_denied(self):
        snapshot = dict(self.snapshot, customer="")
        with self.assertRaises(ValueError):
            project_document_projection_v2(snapshot, "AGREEMENT", "P1", "1.0")

    def test_missing_project_identity_denied(self):
        with self.assertRaises(ValueError):
            project_document_projection_v2(self.snapshot, "INVOICE", "", "1.0")

    def test_missing_version_denied(self):
        with self.assertRaises(ValueError):
            project_document_projection_v2(self.snapshot, "INVOICE", "P1", "")

    def test_source_is_not_mutated(self):
        original = deepcopy(self.snapshot)
        project_document_projection_v2(
            self.snapshot, "CUSTOMER_SOW", "P1", "1.0"
        )
        self.assertEqual(self.snapshot, original)

    def test_no_sending_or_legal_authorization(self):
        for kind in REFERENCE_FILES:
            result = project_document_projection_v2(
                self.snapshot, kind, "P1", "1.0"
            )
            self.assertFalse(result["send_authorized"])
            self.assertFalse(result["legally_eligible_for_installation"])

    def test_equipment_scope_is_limited(self):
        for kind in REFERENCE_FILES:
            result = project_document_projection_v2(
                self.snapshot, kind, "P1", "1.0"
            )
            self.assertEqual(
                "msr_equipment_source" in result,
                kind in {"CUSTOMER_SOW", "INVOICE", "RECEIPT"},
            )