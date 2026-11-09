"""Read-only regression tests for per-physical-unit MSR mapping."""
import unittest
from dataclasses import FrozenInstanceError
from uuid import uuid4

from core.equipment_physical_units import physical_units_from_snapshot

MSR = "11111111-1111-4111-8111-111111111111"


class PhysicalUnitMappingTests(unittest.TestCase):
    def line(self, quantity=1, model="GZV9S", category="New installation"):
        return {
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": model,
            "description": "Test approved equipment description",
            "quantity": quantity,
            "category_of_work": category,
        }

    def units(self, rows=None, **changes):
        arguments = {
            "msr_id": MSR,
            "snapshot": {
                "equipment": [self.line()] if rows is None else rows
            },
        }
        arguments.update(changes)
        return physical_units_from_snapshot(**arguments)

    def test_one_row_with_three_units_produces_three_entries(self):
        units = self.units(rows=[self.line(quantity=3)])
        self.assertEqual(len(units), 3)
        self.assertEqual(
            [unit.unit_id for unit in units],
            [
                "ROW-001-UNIT-001",
                "ROW-001-UNIT-002",
                "ROW-001-UNIT-003",
            ],
        )

    def test_multiple_rows_have_separate_unit_identifiers(self):
        units = self.units(rows=[
            self.line(quantity=3),
            self.line(quantity=1, model="AMST"),
        ])
        self.assertEqual(len(units), 4)
        self.assertEqual(units[3].unit_id, "ROW-002-UNIT-001")
        self.assertEqual(units[3].model_number, "AMST")

    def test_all_approved_details_are_preserved(self):
        source = self.line()
        unit = self.units(rows=[source])[0]
        self.assertEqual(unit.brand, source["brand"])
        self.assertEqual(
            unit.residential_system_type, source["residential_system_type"]
        )
        self.assertEqual(unit.model_number, source["model_number"])
        self.assertEqual(unit.description, source["description"])
        self.assertEqual(unit.category_of_work, source["category_of_work"])

    def test_input_snapshot_is_not_changed(self):
        snapshot = {"equipment": [self.line(quantity=2)]}
        before = {"equipment": [dict(snapshot["equipment"][0])]}
        self.units(snapshot=snapshot)
        self.assertEqual(snapshot, before)

    def test_deterministic_mapping_for_same_msr(self):
        first = self.units(rows=[self.line(quantity=2)])
        second = self.units(rows=[self.line(quantity=2)])
        self.assertEqual(first, second)

    def test_different_msr_keeps_distinct_identity(self):
        first = self.units()
        second = self.units(msr_id=str(uuid4()))
        self.assertNotEqual(first[0].msr_id, second[0].msr_id)
        self.assertEqual(first[0].unit_id, second[0].unit_id)

    def test_legacy_rows_fail_closed_without_invention(self):
        with self.assertRaises(ValueError):
            self.units(rows=[{"description": "Historical air handler"}])

    def test_invalid_quantities_are_rejected(self):
        for quantity in (0, -1, 1.5, True, 1000, "2"):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    self.units(rows=[self.line(quantity=quantity)])

    def test_missing_equipment_and_ninth_row_are_rejected(self):
        for rows in ([], [self.line() for _ in range(9)]):
            with self.subTest(count=len(rows)):
                with self.assertRaises(ValueError):
                    self.units(rows=rows)

    def test_invalid_msr_and_immutable_units(self):
        with self.assertRaises(ValueError):
            self.units(msr_id="not-an-msr")
        with self.assertRaises(FrozenInstanceError):
            self.units()[0].unit_id = "CHANGED"


if __name__ == "__main__":
    unittest.main()