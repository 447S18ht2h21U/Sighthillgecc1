"""Preserve legacy equipment quantities in prepared documents."""
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .documents import format_customer_equipment_line
from .services import validate_snapshot


class LegacyDocumentEquipmentTests(SimpleTestCase):
    def test_approved_legacy_quantity_one_renders(self):
        data = validate_snapshot({
            "equipment": [{"description": "Existing heat pump", "quantity": 1}]
        })
        line = data["equipment"][0]
        self.assertEqual(line["quantity"], "1")
        self.assertEqual(
            format_customer_equipment_line(line),
            "Existing heat pump (quantity 1)",
        )

    def test_approved_legacy_fractional_quantity_renders(self):
        data = validate_snapshot({
            "equipment": [{"description": "Existing item", "quantity": "1.5"}]
        })
        self.assertEqual(
            format_customer_equipment_line(data["equipment"][0]),
            "Existing item (quantity 1.5)",
        )

    def test_new_catalog_quantity_must_be_integer(self):
        line = {
            "brand": "Goodman",
            "residential_system_type": "Heat Pump",
            "model_number": "TEST-100",
            "description": "Catalog equipment",
            "quantity": "1",
        }
        with self.assertRaises(ValueError):
            format_customer_equipment_line(line)

    def test_invalid_historical_quantities_fail_closed(self):
        for quantity in (
            "0", "-1", "NaN", "Infinity", "100001",
            "abc", True, None,
        ):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    format_customer_equipment_line({
                        "description": "Existing item",
                        "quantity": quantity,
                    })

    def test_invalid_legacy_quantity_remains_rejected_on_input(self):
        with self.assertRaises(ValidationError):
            validate_snapshot({
                "equipment": [{"description": "Existing item", "quantity": "-2"}]
            })
