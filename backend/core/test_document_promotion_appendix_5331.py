"""Unpriced promotion disclosure in existing document appendices."""
from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone
from pypdf import PdfReader

from .documents import appendix


def sample_record(other=None):
    snapshot = {
        "customer": "Fictional Customer",
        "contact": "Fictional Customer",
        "billing_address": "123 Test Street",
        "project_location": "123 Test Street",
        "project_city": "Baltimore",
        "project_state": "MD",
        "project_zip": "21201",
        "customer_phone": "301-555-0111",
        "customer_email": "fictional@example.invalid",
        "scope": "Replace fictional HVAC equipment.",
        "equipment": [],
        "materials": [
            {"description": "Ductwork", "quantity": "2"}
        ],
        "base_price": "12500.00",
        "discount": "0.00",
        "tax": "0.00",
        "total_price": "12500.00",
        "payment_option": "100_PERCENT_COMPLETION",
        "payment_terms": "Payment at completion.",
        "commercial_notes": "",
        "financing_type": "NON_FINANCED",
    }
    if other is not None:
        snapshot["other"] = other
    return SimpleNamespace(
        snapshot=snapshot,
        project=SimpleNamespace(code="FICTIONAL-5331"),
        number=1,
    )


def appendix_text(record):
    document = appendix(record, "INVOICE", timezone.now())
    return "\n".join(page.extract_text() or "" for page in document.pages)


class DocumentPromotionAppendix5331(SimpleTestCase):
    def test_cash_back_visible_without_changing_total(self):
        record = sample_record({
            "type": "Cash Back",
            "notes": "Customer receives fictional cash back.",
            "amount": "500.00",
        })
        original_total = record.snapshot["total_price"]
        text = appendix_text(record)
        self.assertIn("Cash Back", text)
        self.assertIn("fictional cash back", text)
        self.assertIn("500.00", text)
        self.assertIn("12,500.00", text)
        self.assertIn("not an additional price deduction", text)
        self.assertEqual(record.snapshot["total_price"], original_total)

    def test_free_water_heater_visible(self):
        record = sample_record({
            "type": "Free Water Heater",
            "notes": "One promotional water heater included.",
            "amount": "0.00",
        })
        text = appendix_text(record)
        self.assertIn("Free Water Heater", text)
        self.assertIn("promotional water heater included", text)

    def test_no_promotion_does_not_invent_one(self):
        text = appendix_text(sample_record())
        self.assertNotIn("Promotional offer / Other", text)

    def test_invalid_promotion_fails_closed(self):
        record = sample_record({
            "type": "Cash Back",
            "notes": "",
            "amount": "500.00",
        })
        with self.assertRaises(ValueError):
            appendix_text(record)
