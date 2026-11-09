"""Focused six-document compatibility and fail-closed regressions."""
from django.test import SimpleTestCase

from .approved_document_compatibility_4247 import (
    CompatibilityDenied,
    describe_compatibility,
    require_exact_approved_kind,
    require_operational_integration,
)
from .approved_six_document_batch_4236 import KINDS
from .models import Document


class DocumentCompatibility4247Tests(SimpleTestCase):
    def test_all_six_approved_kinds_covered(self):
        self.assertEqual(len(KINDS), 6)
        for kind in KINDS:
            with self.subTest(kind=kind):
                result = describe_compatibility(kind)
                self.assertEqual(result.approved_kind, kind)
                self.assertTrue(result.review_only)
                self.assertFalse(result.release_authorized)
                self.assertFalse(result.operationally_integrated)

    def test_existing_legacy_types_match_registered_categories(self):
        registered = {value for value, _ in Document.Kind.choices}
        expected = {
            "CONTRACT",
            "INVOICE",
            "COMPLETION_FINANCED",
            "COMPLETION_NON_FINANCED",
        }
        self.assertEqual(registered, expected)
        for kind in KINDS:
            mapped = describe_compatibility(kind).legacy_kind
            if mapped is not None:
                self.assertIn(mapped, registered)

    def test_sow_and_receipt_have_no_legacy_substitution(self):
        self.assertIsNone(
            describe_compatibility("CUSTOMER_SOW").legacy_kind
        )
        self.assertIsNone(
            describe_compatibility("RECEIPT").legacy_kind
        )

    def test_agreement_has_legacy_contract_correspondence(self):
        result = describe_compatibility("AGREEMENT")
        self.assertEqual(result.legacy_kind, "CONTRACT")
        self.assertFalse(result.operationally_integrated)

    def test_receipt_cannot_substitute_for_invoice(self):
        with self.assertRaises(CompatibilityDenied):
            require_exact_approved_kind("RECEIPT", "INVOICE")

    def test_financing_certificates_cannot_be_interchanged(self):
        with self.assertRaises(CompatibilityDenied):
            require_exact_approved_kind(
                "COMPLETION_FINANCED",
                "COMPLETION_NON_FINANCED",
            )

    def test_exact_identity_stays_review_only(self):
        result = require_exact_approved_kind("INVOICE", "INVOICE")
        self.assertTrue(result.review_only)
        self.assertFalse(result.release_authorized)

    def test_unknown_category_denied(self):
        for kind in ("CONTRACT", "UNKNOWN", "", None):
            with self.subTest(kind=kind):
                with self.assertRaises(CompatibilityDenied):
                    describe_compatibility(kind)

    def test_all_operational_integration_stays_denied(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                with self.assertRaises(CompatibilityDenied):
                    require_operational_integration(kind)