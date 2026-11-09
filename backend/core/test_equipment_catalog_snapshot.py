"""Pure customer-facing equipment snapshot integration tests."""

from types import SimpleNamespace
from unittest import TestCase

from .equipment_catalog_policy import validate_equipment_details
from .equipment_catalog_snapshot import (
    customer_equipment_description,
    snapshot_catalog_item,
    snapshot_equipment_line,
)


class EquipmentCatalogSnapshotTests(TestCase):
    def setUp(self):
        self.values = {
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        }
        self.details = validate_equipment_details(self.values)

    def test_four_fields_and_quantity_preserved(self):
        line = snapshot_equipment_line(self.details, quantity=2)
        self.assertEqual(
            line, {**self.values, "quantity": 2}
        )

    def test_input_changes_do_not_modify_snapshot(self):
        line = snapshot_equipment_line(self.details, quantity=1)
        self.values["description"] = "Later catalog text"
        self.assertEqual(
            line["description"],
            "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        )

    def test_invalid_quantities_rejected(self):
        for quantity in (0, -1, 1000, True, 1.5, "1"):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    snapshot_equipment_line(
                        self.details, quantity=quantity
                    )

    def test_active_catalog_item_can_be_snapshotted(self):
        item = SimpleNamespace(is_active=True, **self.values)
        self.assertEqual(
            snapshot_catalog_item(item, quantity=1),
            {**self.values, "quantity": 1},
        )

    def test_inactive_catalog_item_cannot_be_selected(self):
        item = SimpleNamespace(is_active=False, **self.values)
        with self.assertRaises(ValueError):
            snapshot_catalog_item(item, quantity=1)

    def test_customer_text_includes_all_fields(self):
        line = snapshot_equipment_line(self.details, quantity=1)
        printed = customer_equipment_description(line)
        for value in self.values.values():
            self.assertIn(value, printed)

    def test_legacy_equipment_description_supported(self):
        self.assertEqual(
            customer_equipment_description({
                "description": "Existing equipment",
                "quantity": 1,
            }),
            "Existing equipment",
        )