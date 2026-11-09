"""Isolated regression tests for proposed eight-row equipment mapping."""
from copy import deepcopy
from django.test import SimpleTestCase

from .equipment_invoice_rows import (
    MAX_INVOICE_ROWS,
    WORK_CATEGORIES,
    invoice_equipment_field_values,
    project_equipment_rows,
)


def equipment(category="New installation", number="TEST-100"):
    return {
        "brand": "Goodman",
        "residential_system_type": "Heat Pumps (R-32)",
        "model_number": number,
        "description": "Equipment description from catalog",
        "quantity": 1,
        "category_of_work": category,
    }


class EquipmentInvoiceRowTests(SimpleTestCase):
    def test_eight_row_limit(self):
        self.assertEqual(MAX_INVOICE_ROWS, 8)

    def test_exact_category_choices(self):
        self.assertEqual(WORK_CATEGORIES, {
            "New installation",
            "Replacing existing equipment",
            "Service & maintenance",
        })

    def test_mixed_categories_remain_independent(self):
        data = {"equipment": [
            equipment("New installation"),
            equipment("Replacing existing equipment", "TEST-200"),
            equipment("Service & maintenance", "TEST-300"),
        ]}
        rows = project_equipment_rows(data)
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["category"], "New installation")
        self.assertEqual(rows[1]["category"], "Replacing existing equipment")
        self.assertEqual(rows[2]["category"], "Service & maintenance")
        self.assertEqual(rows[1]["model_number"], "TEST-200")

    def test_eight_entries_are_accepted(self):
        data = {"equipment": [
            equipment(number=f"TEST-{index}")
            for index in range(8)
        ]}
        self.assertEqual(len(project_equipment_rows(data)), 8)

    def test_nine_entries_are_rejected(self):
        with self.assertRaises(ValueError):
            project_equipment_rows({
                "equipment": [equipment() for _ in range(9)]
            })

    def test_blank_slots_are_not_invented_equipment(self):
        rows = project_equipment_rows({"equipment": [equipment()]})
        for row in rows[1:]:
            self.assertTrue(all(value == "" for value in row.values()))

    def test_identifiers_and_prices_are_not_invented(self):
        row = project_equipment_rows({"equipment": [equipment()]})[0]
        self.assertEqual(row["model_identification"], "")
        self.assertEqual(row["serial_number"], "")
        self.assertEqual(row["price"], "")

    def test_legacy_line_is_not_silently_classified(self):
        legacy = {"equipment": [{
            "description": "Existing approved equipment",
            "quantity": 1,
        }]}
        with self.assertRaises(ValueError):
            project_equipment_rows(legacy)

    def test_missing_category_is_rejected(self):
        line = equipment()
        del line["category_of_work"]
        with self.assertRaises(ValueError):
            project_equipment_rows({"equipment": [line]})

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ValueError):
            project_equipment_rows({
                "equipment": [equipment("Unknown")]
            })

    def test_invalid_quantities_are_rejected(self):
        for quantity in (0, -1, 1000, True, "2"):
            with self.subTest(quantity=quantity):
                line = equipment()
                line["quantity"] = quantity
                with self.assertRaises(ValueError):
                    project_equipment_rows({"equipment": [line]})

    def test_original_snapshot_is_not_modified(self):
        data = {"equipment": [equipment()]}
        original = deepcopy(data)
        rows = project_equipment_rows(data)
        rows[0]["brand"] = "Changed"
        self.assertEqual(data, original)

    def test_form_mapping_has_56_unique_fields(self):
        result = invoice_equipment_field_values({
            "equipment": [equipment()]
        })
        self.assertEqual(len(result), 56)
        self.assertEqual(result["line_1_category"], "New installation")
        self.assertEqual(result["line_1_brand"], "Goodman")
        self.assertEqual(result["line_8_category"], "")
        self.assertEqual(result["line_1_serial_number"], "")

    def test_unexpected_fields_are_rejected(self):
        line = equipment()
        line["taxable"] = True
        with self.assertRaises(ValueError):
            project_equipment_rows({"equipment": [line]})

    def test_missing_equipment_list_is_rejected(self):
        with self.assertRaises(ValueError):
            project_equipment_rows({})