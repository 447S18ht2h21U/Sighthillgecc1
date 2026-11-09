"""New eight-row MSR validation with historical compatibility."""
from copy import deepcopy

from rest_framework.exceptions import ValidationError
from django.test import SimpleTestCase

from .services import validate_snapshot


def new_equipment(category="New installation", model="TEST-1"):
    return {
        "brand": "Goodman",
        "residential_system_type": "Heat Pumps (R-32)",
        "model_number": model,
        "description": "Validated catalog description",
        "quantity": 1,
        "category_of_work": category,
    }


class MSREightRowValidationTests(SimpleTestCase):
    def test_one_new_line_accepted(self):
        line = new_equipment()
        result = validate_snapshot({"equipment": [line]})
        self.assertEqual(result["equipment"][0], line)

    def test_mixed_work_types_accepted(self):
        lines = [
            new_equipment("New installation", "TEST-1"),
            new_equipment("Replacing existing equipment", "TEST-2"),
            new_equipment("Service & maintenance", "TEST-3"),
        ]
        result = validate_snapshot({"equipment": lines})
        self.assertEqual(result["equipment"], lines)

    def test_exactly_eight_new_lines_accepted(self):
        lines = [new_equipment(model=f"TEST-{i}") for i in range(8)]
        self.assertEqual(
            len(validate_snapshot({"equipment": lines})["equipment"]), 8
        )

    def test_nine_new_lines_rejected(self):
        lines = [new_equipment(model=f"TEST-{i}") for i in range(9)]
        with self.assertRaises(ValidationError):
            validate_snapshot({"equipment": lines})

    def test_missing_category_among_new_lines_rejected(self):
        first = new_equipment()
        second = new_equipment(model="TEST-2")
        del second["category_of_work"]
        with self.assertRaises(ValidationError):
            validate_snapshot({"equipment": [first, second]})

    def test_invalid_category_rejected(self):
        with self.assertRaises(ValidationError):
            validate_snapshot({
                "equipment": [new_equipment("Unexpected category")]
            })

    def test_legacy_record_remains_valid(self):
        original = {
            "description": "Previously approved equipment",
            "quantity": 1,
        }
        result = validate_snapshot({"equipment": [original]})
        self.assertEqual(result["equipment"][0]["description"],
                         original["description"])
        self.assertNotIn("category_of_work", result["equipment"][0])

    def test_legacy_nine_rows_remain_accepted(self):
        lines = [
            {"description": f"Historical equipment {i}", "quantity": 1}
            for i in range(9)
        ]
        result = validate_snapshot({"equipment": lines})
        self.assertEqual(len(result["equipment"]), 9)

    def test_new_snapshot_not_mutated(self):
        snapshot = {"equipment": [new_equipment()]}
        original = deepcopy(snapshot)
        validate_snapshot(snapshot)
        self.assertEqual(snapshot, original)

    def test_unknown_new_equipment_fields_rejected(self):
        line = new_equipment()
        line["taxable"] = True
        with self.assertRaises(ValidationError):
            validate_snapshot({"equipment": [line]})
