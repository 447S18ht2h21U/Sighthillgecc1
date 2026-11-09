"""Isolated pure-policy tests. No Django database or provider connection."""

import unittest

from core.invoice_delivery_policy import (
    InvoiceDeliveryState,
    assess_existing_invoice_evidence,
)


class InvoiceDeliveryPolicyTests(unittest.TestCase):
    def test_no_evidence_is_not_verified(self):
        result = assess_existing_invoice_evidence()
        self.assertEqual(result.state, InvoiceDeliveryState.NOT_PREPARED)
        self.assertFalse(result.installation_evidence_accepted)

    def test_generated_invoice_is_not_delivery(self):
        result = assess_existing_invoice_evidence(document_generated=True)
        self.assertEqual(result.state, InvoiceDeliveryState.PREPARATION_ONLY)
        self.assertFalse(result.installation_evidence_accepted)

    def test_release_review_is_not_delivery(self):
        result = assess_existing_invoice_evidence(
            document_generated=True,
            release_review_approved=True,
        )
        self.assertEqual(result.state, InvoiceDeliveryState.RELEASE_REVIEW_APPROVED)
        self.assertFalse(result.installation_evidence_accepted)

    def test_delivery_claim_without_verification_is_rejected(self):
        result = assess_existing_invoice_evidence(
            document_generated=True,
            release_review_approved=True,
            delivery_claimed=True,
        )
        self.assertEqual(result.state, InvoiceDeliveryState.DELIVERY_UNVERIFIED)
        self.assertFalse(result.installation_evidence_accepted)

    def test_delivery_claim_cannot_override_missing_preparation(self):
        result = assess_existing_invoice_evidence(delivery_claimed=True)
        self.assertFalse(result.installation_evidence_accepted)

    def test_every_existing_boolean_combination_is_fail_closed(self):
        from itertools import product
        for generated, approved, claimed in product((False, True), repeat=3):
            with self.subTest(generated=generated, approved=approved, claimed=claimed):
                result = assess_existing_invoice_evidence(
                    document_generated=generated,
                    release_review_approved=approved,
                    delivery_claimed=claimed,
                )
                self.assertFalse(result.installation_evidence_accepted)
                self.assertNotEqual(result.state, InvoiceDeliveryState.DELIVERY_VERIFIED)

    def test_non_boolean_flags_are_rejected(self):
        for invalid in ("true", 1, None, [], {}):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(TypeError):
                    assess_existing_invoice_evidence(document_generated=invalid)

    def test_assessment_is_immutable(self):
        from dataclasses import FrozenInstanceError
        result = assess_existing_invoice_evidence()
        with self.assertRaises(FrozenInstanceError):
            result.installation_evidence_accepted = True

    def test_state_names_are_explicit(self):
        self.assertEqual(
            InvoiceDeliveryState.DELIVERY_VERIFIED.value,
            "DELIVERY_VERIFIED",
        )
        self.assertNotEqual(
            InvoiceDeliveryState.RELEASE_REVIEW_APPROVED,
            InvoiceDeliveryState.DELIVERY_VERIFIED,
        )


if __name__ == "__main__":
    unittest.main()