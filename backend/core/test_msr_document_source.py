"""MSR data provenance and customer-document consistency checks."""

from unittest import TestCase

from .msr_document_source import (
    customer_document_data,
    document_customer_name,
    invoice_other_display,
    invoice_other_notes,
    msr_other_details,
)


class MSRDocumentSourceTests(TestCase):
    def setUp(self):
        self.snapshot = {
            "customer": "Mary Johnson",
            "billing_address": "123 Example Road",
            "project_location": "123 Example Road",
            "project_city": "Example",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "",
            "customer_email": "",
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pumps (R-32)",
                "model_number": "GZV9S",
                "description": "Up to 21.0 SEER2",
                "quantity": 1,
            }],
            "other": {
                "type": "Reduced Price",
                "amount": "500.00",
                "notes": "Approved customer price reduction",
            },
        }

    def test_customer_name_is_taken_verbatim_from_msr(self):
        self.assertEqual(document_customer_name(self.snapshot), "Mary Johnson")

    def test_shared_customer_fields_are_copied(self):
        copied = customer_document_data(self.snapshot)
        self.assertEqual(copied["project_state"], "MD")
        self.assertEqual(copied["customer"], "Mary Johnson")

    def test_snapshot_equipment_is_independent(self):
        copied = customer_document_data(self.snapshot)
        self.snapshot["equipment"][0]["model_number"] = "CHANGED"
        self.assertEqual(copied["equipment"][0]["model_number"], "GZV9S")

    def test_empty_customer_name_is_rejected(self):
        self.snapshot["customer"] = ""
        with self.assertRaises(ValueError):
            document_customer_name(self.snapshot)

    def test_discount_is_negative_on_invoice(self):
        self.assertEqual(invoice_other_display(self.snapshot), "-500.00")

    def test_notes_follow_msr_other(self):
        self.assertEqual(
            invoice_other_notes(self.snapshot),
            "Reduced Price: Approved customer price reduction",
        )

    def test_free_equipment_does_not_double_subtract(self):
        self.snapshot["other"]["type"] = "Free Water Heater"
        self.assertIsNone(invoice_other_display(self.snapshot))

    def test_cash_back_does_not_automatically_reduce_invoice(self):
        self.snapshot["other"]["type"] = "Cash Back"
        self.assertIsNone(invoice_other_display(self.snapshot))

    def test_invalid_other_amount_denied(self):
        self.snapshot["other"]["amount"] = "-100"
        with self.assertRaises(ValueError):
            msr_other_details(self.snapshot)