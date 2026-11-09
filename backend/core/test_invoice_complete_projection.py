from copy import deepcopy
from django.test import SimpleTestCase

from .invoice_msr_projection import complete_invoice_projection


def equipment(category, model):
    return {
        "brand": "Goodman",
        "residential_system_type": "Heat Pumps (R-32)",
        "model_number": model,
        "description": "Catalog description",
        "quantity": 1,
        "category_of_work": category,
    }


def snapshot():
    return {
        "customer": "Mary Example",
        "base_price": "10000.00",
        "discount": "500.00",
        "tax": "0.00",
        "total_price": "9500.00",
        "other": {
            "type": "Reduced Price",
            "amount": "500.00",
            "notes": "Approved promotional price reduction",
        },
        "equipment": [
            equipment("New installation", "TEST-A"),
            equipment("Replacing existing equipment", "TEST-B"),
        ],
    }


class CompleteInvoiceProjectionTests(SimpleTestCase):
    def test_financial_values(self):
        result = complete_invoice_projection(snapshot())
        self.assertEqual(result["customer_name"], "Mary Example")
        self.assertEqual(result["subtotal"], "10,000.00")
        self.assertEqual(result["other_charges"], "-500.00")
        self.assertEqual(result["sales_tax"], "0.00")
        self.assertEqual(result["invoice_total"], "9,500.00")

    def test_equipment_categories_and_models(self):
        result = complete_invoice_projection(snapshot())
        self.assertEqual(result["line_1_category"], "New installation")
        self.assertEqual(result["line_2_category"], "Replacing existing equipment")
        self.assertEqual(result["line_1_model_number"], "TEST-A")
        self.assertEqual(result["line_2_model_number"], "TEST-B")

    def test_expected_field_count(self):
        self.assertEqual(len(complete_invoice_projection(snapshot())), 62)

    def test_unused_lines_are_blank(self):
        result = complete_invoice_projection(snapshot())
        self.assertEqual(result["line_3_category"], "")
        self.assertEqual(result["line_8_model_number"], "")

    def test_installation_details_not_invented(self):
        result = complete_invoice_projection(snapshot())
        for number in range(1, 9):
            self.assertEqual(result[f"line_{number}_serial_number"], "")
            self.assertEqual(result[f"line_{number}_model_identification"], "")
            self.assertEqual(result[f"line_{number}_price"], "")

    def test_input_snapshot_is_unchanged(self):
        data = snapshot()
        original = deepcopy(data)
        result = complete_invoice_projection(data)
        result["line_1_brand"] = "Changed"
        self.assertEqual(data, original)

    def test_ninth_equipment_line_rejected(self):
        data = snapshot()
        data["equipment"] = [
            equipment("New installation", f"TEST-{i}") for i in range(9)
        ]
        with self.assertRaises(ValueError):
            complete_invoice_projection(data)

    def test_missing_category_rejected(self):
        data = snapshot()
        del data["equipment"][0]["category_of_work"]
        with self.assertRaises(ValueError):
            complete_invoice_projection(data)

    def test_inconsistent_total_rejected(self):
        data = snapshot()
        data["total_price"] = "10000.00"
        with self.assertRaises(ValueError):
            complete_invoice_projection(data)