"""Tests for conservative individual compensation evidence labels."""

from django.test import SimpleTestCase

from .individual_compensation_report_evidence_policy import (
    historical_msr_label,
    installation_completion_evidence_label,
    payment_evidence_label,
    project_association_label,
)


class IndividualCompensationEvidencePolicyTests(SimpleTestCase):

    def test_explicit_project_association(self):
        self.assertEqual(
            project_association_label(True),
            "Project-associated",
        )

    def test_missing_project_association(self):
        self.assertEqual(
            project_association_label(False),
            "Not assigned to a project",
        )

    def test_invalid_project_flag_rejected(self):
        with self.assertRaises(ValueError):
            project_association_label("yes")

    def test_historical_msr_without_binding(self):
        self.assertEqual(
            historical_msr_label(False),
            "Historical MSR version not established",
        )

    def test_historical_msr_with_explicit_binding(self):
        self.assertEqual(
            historical_msr_label(True),
            "Historical MSR binding recorded",
        )

    def test_draft_compensation_not_approved(self):
        self.assertEqual(
            payment_evidence_label(
                "DRAFT", False, False, contractor=True
            ),
            "Draft - Not Approved",
        )

    def test_approved_compensation_not_issued(self):
        self.assertEqual(
            payment_evidence_label(
                "APPROVED", False, False, contractor=True
            ),
            "Approved - Not Yet Issued",
        )

    def test_contractor_issued_not_settled(self):
        self.assertEqual(
            payment_evidence_label(
                "APPROVED", True, False, contractor=True
            ),
            "Payment Issued - Not Yet Marked Paid",
        )

    def test_contractor_settled_not_marked_paid(self):
        self.assertEqual(
            payment_evidence_label(
                "APPROVED", True, True, contractor=True
            ),
            "Settlement Verified - Not Yet Marked Paid",
        )

    def test_contractor_paid_with_verified_settlement(self):
        self.assertEqual(
            payment_evidence_label(
                "PAID", True, True, contractor=True
            ),
            "Paid",
        )

    def test_paid_contractor_without_settlement_rejected(self):
        with self.assertRaises(ValueError):
            payment_evidence_label(
                "PAID", True, False, contractor=True
            )

    def test_paid_without_issuance_rejected(self):
        with self.assertRaises(ValueError):
            payment_evidence_label(
                "PAID", False, False, contractor=False
            )

    def test_settlement_without_issuance_rejected(self):
        with self.assertRaises(ValueError):
            payment_evidence_label(
                "APPROVED", False, True, contractor=True
            )

    def test_employee_paid_with_issuance(self):
        self.assertEqual(
            payment_evidence_label(
                "PAID", True, False, contractor=False
            ),
            "Paid",
        )

    def test_employee_cannot_claim_contractor_settlement(self):
        with self.assertRaises(ValueError):
            payment_evidence_label(
                "PAID", True, True, contractor=False
            )

    def test_provider_completion_requires_explicit_verification(self):
        self.assertEqual(
            installation_completion_evidence_label(False),
            "Provider-Verified Completion Not Established",
        )
        self.assertEqual(
            installation_completion_evidence_label(True),
            "Provider-Verified Completion",
        )
        with self.assertRaises(ValueError):
            installation_completion_evidence_label(None)