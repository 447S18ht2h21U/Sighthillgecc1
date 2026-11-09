"""MSR source-of-truth validation: catalog equipment and Other."""

from copy import deepcopy
from unittest import TestCase

from rest_framework.exceptions import ValidationError

from .services import validate_snapshot


class MSREquipmentOtherValidationTests(TestCase):
    def setUp(self):
        self.data = {
            "customer": "Mary Johnson",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pumps (R-32)",
                "model_number": "GZV9S",
                "description": "Up to 21.0 SEER2",
                "quantity": 2,
            }],
            "other": {
                "type": "Reduced Price",
                "amount": "500.00",
                "notes": "Approved selling-price reduction",
            },
            "base_price": "12000.00",
            "discount": "500.00",
            "tax": "0.00",
            "total_price": "11500.00",
        }

    def test_catalog_equipment_is_accepted(self):
        result = validate_snapshot(deepcopy(self.data))
        self.assertEqual(result["equipment"][0]["model_number"], "GZV9S")
        self.assertEqual(result["equipment"][0]["quantity"], 2)

    def test_other_is_preserved_and_normalized(self):
        result = validate_snapshot(deepcopy(self.data))
        self.assertEqual(result["other"]["type"], "Reduced Price")
        self.assertEqual(result["other"]["amount"], "500.00")

    def test_mismatched_reduced_price_is_rejected(self):
        self.data["other"]["amount"] = "250.00"
        with self.assertRaises(ValidationError):
            validate_snapshot(self.data)

    def test_catalog_quantity_must_be_integer(self):
        self.data["equipment"][0]["quantity"] = "2"
        with self.assertRaises(ValidationError):
            validate_snapshot(self.data)

    def test_incomplete_catalog_equipment_is_rejected(self):
        del self.data["equipment"][0]["residential_system_type"]
        with self.assertRaises(ValidationError):
            validate_snapshot(self.data)

    def test_legacy_equipment_is_accepted(self):
        self.data["equipment"] = [{
            "description": "Previously approved equipment",
            "quantity": 1,
        }]
        result = validate_snapshot(self.data)
        self.assertEqual(result["equipment"][0]["quantity"], "1")

    def test_free_equipment_is_not_price_discount(self):
        self.data["other"] = {
            "type": "Free Water Heater",
            "amount": "600.00",
            "notes": "Free Goodman water heater, quantity one",
        }
        self.data["discount"] = "0.00"
        self.data["total_price"] = "12000.00"
        result = validate_snapshot(self.data)
        self.assertEqual(result["other"]["type"], "Free Water Heater")
        self.assertEqual(result["discount"], "0.00")

    def test_absent_other_keeps_legacy_msr_compatible(self):
        del self.data["other"]
        result = validate_snapshot(self.data)
        self.assertNotIn("other", result)