"""Customer-facing equipment information in document appendices."""

from unittest import TestCase

from .documents import format_customer_equipment_line


class EquipmentCatalogDocumentTests(TestCase):
    def setUp(self):
        self.line = {
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
            "quantity": 2,
        }

    def test_all_four_fields_and_quantity_are_visible(self):
        result = format_customer_equipment_line(self.line)
        for value in self.line.values():
            self.assertIn(str(value), result)

    def test_legacy_equipment_is_supported(self):
        self.assertEqual(
            format_customer_equipment_line({
                "description": "Existing approved equipment",
                "quantity": 1,
            }),
            "Existing approved equipment (quantity 1)",
        )

    def test_model_family_wildcard_remains_verbatim(self):
        self.line["model_number"] = "AMST*13"
        self.assertIn(
            "AMST*13",
            format_customer_equipment_line(self.line),
        )

    def test_incomplete_catalog_line_is_rejected(self):
        del self.line["residential_system_type"]
        with self.assertRaises(ValueError):
            format_customer_equipment_line(self.line)

    def test_invalid_quantities_are_rejected(self):
        for quantity in (0, -1, 1000, True, "2"):
            with self.subTest(quantity=quantity):
                self.line["quantity"] = quantity
                with self.assertRaises(ValueError):
                    format_customer_equipment_line(self.line)