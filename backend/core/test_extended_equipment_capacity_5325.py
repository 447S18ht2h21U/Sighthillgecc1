"""Focused equipment-capacity regression; disposable test database only."""
from uuid import uuid4
from django.test import SimpleTestCase

from .equipment_invoice_rows import (
    project_equipment_rows,
    invoice_equipment_field_values,
)
from .equipment_physical_units import physical_units_from_snapshot
from .services import validate_snapshot


def equipment_row(index):
    return {
        "brand": "Goodman",
        "residential_system_type": "Air conditioning",
        "model_number": f"TEST-{index:03d}",
        "description": f"Fictional equipment {index}",
        "quantity": 1,
        "category_of_work": "Replacing existing equipment",
    }


class ExtendedEquipmentCapacity5325(SimpleTestCase):
    def test_twelve_equipment_rows_preserved_without_unit_prices(self):
        snapshot = {"equipment": [equipment_row(i) for i in range(12)]}
        validated = validate_snapshot(snapshot)
        rows = project_equipment_rows(validated)
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[-1]["model_number"], "TEST-011")
        self.assertTrue(all(row["price"] == "" for row in rows))
        fields = invoice_equipment_field_values(validated)
        self.assertEqual(fields["line_12_model_number"], "TEST-011")

    def test_existing_short_document_mapping_remains_eight_rows(self):
        rows = project_equipment_rows({
            "equipment": [equipment_row(0), equipment_row(1)]
        })
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[2]["model_number"], "")

    def test_physical_units_preserved_beyond_eight_rows(self):
        snapshot = {"equipment": [equipment_row(i) for i in range(12)]}
        units = physical_units_from_snapshot(
            msr_id=str(uuid4()), snapshot=snapshot
        )
        self.assertEqual(len(units), 12)
        self.assertEqual(units[-1].unit_id, "ROW-012-UNIT-001")

    def test_backend_capacity_guard_remains(self):
        snapshot = {"equipment": [equipment_row(i) for i in range(101)]}
        with self.assertRaises(ValueError):
            project_equipment_rows(snapshot)
