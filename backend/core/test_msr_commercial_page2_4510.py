"""Isolated discount/promotion and commercial overlay regression."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfReader

from .msr_commercial_page2_4510 import (
    page_two_commercial_data,
    fictional_commercial_sow_preview,
)


class MSRCommercial4510Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdf = (
            Path(__file__).resolve().parents[2]
            / "docs/reference/GECC-20261107-final-seven"
            / "GECC Project Scope of Work 20261107v2.pdf"
        )

    def setUp(self):
        self.snapshot = {
            "customer": "FICTIONAL AVERY SAMPLE",
            "billing_address": "123 Fictional Lane",
            "project_location": "123 Fictional Lane",
            "project_city": "Sample City",
            "project_state": "MD",
            "project_zip": "00000",
            "customer_phone": "555-0100",
            "customer_email": "avery@example.invalid",
            "equipment": [],
            "description_of_work": "New installation",
            "scope": "Fictional HVAC equipment installation.",
            "financing_type": "NON_FINANCED",
            "payment_method": "EFT",
            "base_price": "12000.00",
            "discount": "1000.00",
            "tax": "0.00",
            "total_price": "11000.00",
            "other": {
                "type": "Marketing Promotion",
                "amount": "1000.00",
                "notes": "Fictional approved-price-reduction example",
            },
        }

    def render(self, source=None):
        return fictional_commercial_sow_preview(
            self.pdf.read_bytes() if source is None else source,
            self.snapshot, "TEST-001", "V1",
            "2026-11-08", "FICTIONAL SALES ASSOCIATE",
        )

    def test_marketing_discount_reduces_retail_price(self):
        data = page_two_commercial_data(self.snapshot)
        self.assertEqual(data["price_discount"], "1,000.00")
        self.assertEqual(data["customer_total"], "11,000.00")
        self.assertTrue(data["discount_requires_ceo_approval"])
        self.assertFalse(data["ceo_approval_verified"])

    def test_cash_back_never_reduces_retail(self):
        self.snapshot["discount"] = "0.00"
        self.snapshot["total_price"] = "12000.00"
        self.snapshot["other"] = {
            "type": "Cash Back", "amount": "1000.00",
            "notes": "Fictional cash-back benefit",
        }
        data = page_two_commercial_data(self.snapshot)
        self.assertEqual(data["customer_total"], "12,000.00")
        self.assertEqual(data["price_discount"], "0.00")

    def test_free_water_heater_never_reduces_retail(self):
        self.snapshot["discount"] = "0.00"
        self.snapshot["total_price"] = "12000.00"
        self.snapshot["other"] = {
            "type": "Free Water Heater", "amount": "800.00",
            "notes": "Fictional company-paid equipment",
        }
        data = page_two_commercial_data(self.snapshot)
        self.assertEqual(data["customer_total"], "12,000.00")
        self.assertEqual(data["price_discount"], "0.00")

    def test_nonprice_promotion_with_discount_rejected(self):
        self.snapshot["other"]["type"] = "Cash Back"
        with self.assertRaises(ValueError):
            page_two_commercial_data(self.snapshot)

    def test_marketing_promotion_without_discount_rejected(self):
        self.snapshot["discount"] = "0.00"
        self.snapshot["total_price"] = "12000.00"
        with self.assertRaises(ValueError):
            page_two_commercial_data(self.snapshot)

    def test_discount_must_match_marketing_amount(self):
        self.snapshot["other"]["amount"] = "900.00"
        with self.assertRaises(ValueError):
            page_two_commercial_data(self.snapshot)

    def test_pdf_two_pages_and_fictional_amounts(self):
        pdf = PdfReader(BytesIO(self.render()), strict=True)
        self.assertEqual(len(pdf.pages), 2)
        text = pdf.pages[1].extract_text()
        for value in ("12,000.00", "1,000.00", "11,000.00", "5,500.00"):
            self.assertIn(value, text)
        self.assertFalse(pdf.get_fields())

    def test_original_pdf_and_snapshot_unchanged(self):
        before_pdf = sha256(self.pdf.read_bytes()).digest()
        before_snapshot = deepcopy(self.snapshot)
        self.render()
        self.assertEqual(sha256(self.pdf.read_bytes()).digest(), before_pdf)
        self.assertEqual(self.snapshot, before_snapshot)
