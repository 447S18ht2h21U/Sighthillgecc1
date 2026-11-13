"""Real-service equipment adjudication integration into Receipt readiness."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from . import test_equipment_full_chain_4788 as full_chain
from .final_receipt_adjudication_readiness_4789 import (
    assess_final_receipt_adjudication_readiness,
)


MODULE = "core.final_receipt_adjudication_readiness_4789"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class FinalReceiptAdjudicationReadinessTests4789(TestCase):
    setUp = full_chain.FullEquipmentEvidenceChain4788.setUp
    prepare_real_evidence = (
        full_chain.FullEquipmentEvidenceChain4788.prepare_real_evidence
    )
    decide = full_chain.FullEquipmentEvidenceChain4788.decide

    def boundary(self, *, reviewed, **changes):
        values = dict(
            project_id=str(self.project.pk),
            msr_id=str(self.msr.pk),
            internal_document_verified=False,
            reviewed_equipment_candidates_complete=reviewed,
            trusted_installation_evidence=False,
            customer_receipt_issuance_authorized=False,
            provider_email_authenticated=False,
            customer_delivery_verified=False,
            completion_authorized=False,
            blockers=("No FINAL customer Receipt is retained.",),
        )
        values.update(changes)
        return SimpleNamespace(**values)

    def assess(self, *, reviewed, **changes):
        with patch(
            MODULE + ".assess_final_receipt_issuance_boundary",
            return_value=self.boundary(reviewed=reviewed, **changes),
        ):
            return assess_final_receipt_adjudication_readiness(
                self.project
            )

    def assert_blocked(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertTrue(result.blockers)

    def test_real_complete_chain_reports_only_provisional_adjudication(self):
        manifest = self.prepare_real_evidence()
        self.assertTrue(manifest.all_candidates_reviewed)

        for unit in manifest.reviewed_units:
            self.decide(unit.unit_id)

        result = self.assess(reviewed=True)

        self.assertTrue(result.candidate_equipment_review_complete)
        self.assertTrue(result.provisional_ceo_adjudication_complete)
        self.assertEqual(
            result.verified_ceo_approvals,
            len(manifest.reviewed_units),
        )
        self.assertEqual(
            result.expected_equipment_units,
            len(manifest.reviewed_units),
        )
        self.assert_blocked(result)
        print(
            "PASS: Real equipment approvals appear in Receipt readiness "
            "without issuing a Receipt."
        )

    def test_real_missing_ceo_decision_remains_blocked(self):
        manifest = self.prepare_real_evidence()
        self.assertTrue(manifest.all_candidates_reviewed)

        result = self.assess(reviewed=True)
        self.assertFalse(result.provisional_ceo_adjudication_complete)
        self.assertEqual(result.verified_ceo_approvals, 0)
        self.assert_blocked(result)
        print("PASS: Missing CEO adjudication is reported as blocked.")

    def test_rejected_ceo_decision_remains_blocked(self):
        manifest = self.prepare_real_evidence()

        for index, unit in enumerate(manifest.reviewed_units):
            self.decide(unit.unit_id, approve=(index != 0))

        result = self.assess(reviewed=True)
        self.assertFalse(result.provisional_ceo_adjudication_complete)
        self.assert_blocked(result)
        print("PASS: Rejected CEO decision cannot unblock Receipt.")

    def test_missing_physical_review_and_false_boundary_trust(self):
        missing = self.assess(reviewed=False)
        self.assertFalse(missing.candidate_equipment_review_complete)
        self.assertFalse(missing.provisional_ceo_adjudication_complete)
        self.assert_blocked(missing)

        for altered in (
            {"customer_receipt_issuance_authorized": True},
            {"trusted_installation_evidence": True},
            {"customer_delivery_verified": True},
            {"msr_id": "FOREIGN-MSR"},
        ):
            with self.assertRaises(ValueError):
                self.assess(reviewed=False, **altered)

        print(
            "PASS: Incomplete inspection, false authority, "
            "and cross-MSR binding rejected."
        )
