"""Isolated binding tests: no database, migrations, or provider calls."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from core.invoice_delivery_evidence import assess_delivery_candidate
from core.invoice_delivery_binding import verify_candidate_binding

M = "11111111-1111-4111-8111-111111111111"
D = "22222222-2222-4222-8222-222222222222"
P = "33333333-3333-4333-8333-333333333333"
V = "44444444-4444-4444-8444-444444444444"
OLD = "55555555-5555-4555-8555-555555555555"
NOW = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)


class InvoiceBindingTests(unittest.TestCase):
    def candidate(self):
        return assess_delivery_candidate(
            msr_id=M, document_id=D, invoice_sha256="a" * 64,
            recipient_email="customer@example.invalid",
            channel="PROVIDER_EMAIL", provider_reference="FICTIONAL-RECEIPT",
            delivered_at=NOW, verified_by_id=V, verified_at=NOW,
            prepared_by_id=P, now=NOW,
        )

    def expected(self, **changes):
        data = dict(
            current_approved_msr_id=M,
            expected_document_id=D,
            expected_pdf_sha256="a" * 64,
            expected_recipient_email="customer@example.invalid",
            expected_document_kind="INVOICE",
            document_status="PREPARATION",
            document_msr_id=M,
        )
        data.update(changes)
        return data

    def test_exact_binding_still_does_not_prove_delivery(self):
        result = verify_candidate_binding(self.candidate(), **self.expected())
        self.assertTrue(result.candidate_matches)
        self.assertFalse(result.trusted_delivery)
        self.assertFalse(result.installation_evidence_accepted)

    def test_revised_msr_blocks_old_receipt(self):
        result = verify_candidate_binding(
            self.candidate(), **self.expected(current_approved_msr_id=OLD)
        )
        self.assertFalse(result.candidate_matches)

    def test_document_from_other_msr_blocks(self):
        result = verify_candidate_binding(
            self.candidate(), **self.expected(document_msr_id=OLD)
        )
        self.assertFalse(result.candidate_matches)

    def test_other_invoice_blocks(self):
        result = verify_candidate_binding(
            self.candidate(), **self.expected(expected_document_id=OLD)
        )
        self.assertFalse(result.candidate_matches)

    def test_changed_pdf_blocks(self):
        result = verify_candidate_binding(
            self.candidate(), **self.expected(expected_pdf_sha256="b" * 64)
        )
        self.assertFalse(result.candidate_matches)

    def test_wrong_recipient_blocks(self):
        result = verify_candidate_binding(
            self.candidate(),
            **self.expected(expected_recipient_email="other@example.invalid")
        )
        self.assertFalse(result.candidate_matches)

    def test_wrong_document_kind_blocks(self):
        result = verify_candidate_binding(
            self.candidate(), **self.expected(expected_document_kind="CONTRACT")
        )
        self.assertFalse(result.candidate_matches)

    def test_unknown_status_blocks(self):
        result = verify_candidate_binding(
            self.candidate(), **self.expected(document_status="SENT")
        )
        self.assertFalse(result.candidate_matches)

    def test_self_claimed_trust_blocks(self):
        forged = replace(self.candidate(), trusted_delivery=True)
        with self.assertRaises(ValueError):
            verify_candidate_binding(forged, **self.expected())

    def test_self_claimed_installation_authority_blocks(self):
        forged = replace(
            self.candidate(), installation_evidence_accepted=True
        )
        with self.assertRaises(ValueError):
            verify_candidate_binding(forged, **self.expected())

    def test_result_is_immutable(self):
        from dataclasses import FrozenInstanceError
        result = verify_candidate_binding(self.candidate(), **self.expected())
        with self.assertRaises(FrozenInstanceError):
            result.installation_evidence_accepted = True


if __name__ == "__main__":
    unittest.main()