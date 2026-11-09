"""Pure, side-effect-free revised Invoice mapping tests."""

from copy import deepcopy
from unittest import TestCase

from .invoice_msr_projection import revised_invoice_projection


class RevisedInvoiceProjectionTests(TestCase):
    def setUp(self):
        self.msr = {
            "customer": "Mary Johnson",
            "base_price": "10000.00",
            "discount": "500.00",
            "tax": "0.00",
            "total_price": "9500.00",
            "other": {
                "type": "Reduced Price",
                "amount": "500.00",
                "notes": "Approved customer price reduction",
            },
        }

    def test_negative_other_and_original_subtotal(self):
        result = revised_invoice_projection(self.msr)
        self.assertEqual(result["subtotal"], "10,000.00")
        self.assertEqual(result["other_charges"], "-500.00")
        self.assertEqual(result["invoice_total"], "9,500.00")

    def test_customer_name_and_notes_come_from_msr(self):
        result = revised_invoice_projection(self.msr)
        self.assertEqual(result["customer_name"], "Mary Johnson")
        self.assertEqual(
            result["notes"],
            "Reduced Price: Approved customer price reduction",
        )

    def test_projection_does_not_modify_snapshot(self):
        original = deepcopy(self.msr)
        revised_invoice_projection(self.msr)
        self.assertEqual(self.msr, original)

    def test_marketing_promotion_can_reduce_price_once(self):
        self.msr["other"]["type"] = "Marketing Promotion"
        result = revised_invoice_projection(self.msr)
        self.assertEqual(result["other_charges"], "-500.00")

    def test_free_equipment_does_not_reduce_total(self):
        self.msr["other"] = {
            "type": "Free Water Heater",
            "amount": "600.00",
            "notes": "Goodman water heater, quantity one, supplied free",
        }
        self.msr["discount"] = "0.00"
        self.msr["total_price"] = "10000.00"
        result = revised_invoice_projection(self.msr)
        self.assertEqual(result["other_charges"], "0.00")
        self.assertIn("Goodman water heater", result["notes"])

    def test_cash_back_does_not_silently_reduce_price(self):
        self.msr["other"]["type"] = "Cash Back"
        with self.assertRaises(ValueError):
            revised_invoice_projection(self.msr)

    def test_legacy_msr_discount_supported(self):
        del self.msr["other"]
        result = revised_invoice_projection(self.msr)
        self.assertEqual(result["other_charges"], "-500.00")
        self.assertIn("MSR price reduction", result["notes"])

    def test_mismatched_promotion_is_rejected(self):
        self.msr["other"]["amount"] = "250.00"
        with self.assertRaises(ValueError):
            revised_invoice_projection(self.msr)

    def test_inconsistent_total_is_rejected(self):
        self.msr["total_price"] = "10000.00"
        with self.assertRaises(ValueError):
            revised_invoice_projection(self.msr)