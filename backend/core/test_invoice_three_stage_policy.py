"""Tests for approved three-stage Invoice policy foundation."""
import unittest
from dataclasses import FrozenInstanceError

from core.invoice_three_stage_policy import (
    InvoiceStage,
    assess_pre_installation,
    assess_equipment_identification,
    assess_post_installation_delivery,
)


class ThreeStageInvoicePolicyTests(unittest.TestCase):
    def pre(self, **changes):
        flags = dict(
            approved_msr=True,
            contract_signed=True,
            cancellation_cleared=True,
            waiting_period_cleared=True,
            payment_cleared=True,
        )
        flags.update(changes)
        return assess_pre_installation(**flags)

    def equipment(self, **changes):
        flags = dict(
            physical_units_accounted_for=True,
            serials_recorded_or_exceptions_approved=True,
        )
        flags.update(changes)
        return assess_equipment_identification(**flags)

    def post(self, **changes):
        flags = dict(
            installation_completed=True,
            final_invoice_prepared=True,
            versioned_addendum_prepared=True,
            independently_verified_delivery=True,
        )
        flags.update(changes)
        return assess_post_installation_delivery(**flags)

    def test_pre_installation_has_no_invoice_signature_requirement(self):
        result = self.pre()
        self.assertEqual(result.stage, InvoiceStage.PRE_INSTALLATION)
        self.assertTrue(result.requirements_satisfied)
        self.assertFalse(result.installation_authorized)

    def test_missing_contract_blocks_preparation(self):
        result = self.pre(contract_signed=False)
        self.assertIn("contract_signed", result.outstanding)
        self.assertFalse(result.requirements_satisfied)

    def test_cancellation_and_waiting_are_separate(self):
        result = self.pre(
            cancellation_cleared=False,
            waiting_period_cleared=False,
        )
        self.assertEqual(
            result.outstanding,
            ("cancellation_cleared", "waiting_period_cleared"),
        )

    def test_payment_is_required(self):
        self.assertFalse(
            self.pre(payment_cleared=False).requirements_satisfied
        )

    def test_equipment_identification_requires_every_unit(self):
        result = self.equipment(physical_units_accounted_for=False)
        self.assertFalse(result.requirements_satisfied)

    def test_serials_or_approved_exceptions_required(self):
        result = self.equipment(
            serials_recorded_or_exceptions_approved=False
        )
        self.assertIn(
            "serials_recorded_or_exceptions_approved",
            result.outstanding,
        )

    def test_post_installation_requires_completion(self):
        result = self.post(installation_completed=False)
        self.assertFalse(result.requirements_satisfied)

    def test_final_invoice_and_addendum_are_separate(self):
        result = self.post(
            final_invoice_prepared=False,
            versioned_addendum_prepared=False,
        )
        self.assertEqual(len(result.outstanding), 2)

    def test_claimed_delivery_never_authenticates_itself(self):
        result = self.post()
        self.assertTrue(result.requirements_satisfied)
        self.assertFalse(result.delivery_verified)
        self.assertFalse(result.installation_authorized)

    def test_flags_and_results_are_strict(self):
        with self.assertRaises(ValueError):
            self.pre(contract_signed="true")
        with self.assertRaises(ValueError):
            self.post(independently_verified_delivery=1)
        with self.assertRaises(TypeError):
            assess_pre_installation(approved_msr=True)
        with self.assertRaises(FrozenInstanceError):
            self.pre().installation_authorized = True


if __name__ == "__main__":
    unittest.main()