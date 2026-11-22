"""Focused customer-document continuation tests."""
from io import BytesIO
from django.test import SimpleTestCase
from pypdf import PdfReader

from .customer_schedule_continuation_5326 import (
    render_schedule_continuation,
)


def equipment(index):
    return {
        "brand": "Goodman",
        "residential_system_type": "Air conditioning",
        "model_number": f"DEMO-{index:03d}",
        "description": f"Fictional equipment {index}",
        "quantity": 1,
        "category_of_work": "Replacing existing equipment",
    }


class ContinuationPages5326A(SimpleTestCase):
    def build(self, equipment_count, material_count, notes=None):
        snapshot = {
            "equipment": [
                equipment(i) for i in range(equipment_count)
            ],
            "materials": [
                {
                    "description": f"Fictional material {i}",
                    "quantity": "2",
                }
                for i in range(material_count)
            ],
        }
        pdf = render_schedule_continuation(
            snapshot=snapshot,
            project_code="104-SA-2026-11-22",
            document_kind="RECEIPT",
            equipment_start=8,
            promotion_notes=notes,
        )
        if not pdf:
            return None, ""
        reader = PdfReader(BytesIO(pdf))
        text = "\\n".join(
            page.extract_text() for page in reader.pages
        )
        return reader, text

    def test_twelve_equipment_entries_and_materials(self):
        reader, text = self.build(12, 12)
        self.assertGreaterEqual(len(reader.pages), 1)
        self.assertIn("DEMO-008", text)
        self.assertIn("DEMO-011", text)
        self.assertNotIn("DEMO-007", text)
        self.assertIn("Fictional material 0", text)
        self.assertIn("Fictional material 11", text)
        self.assertIn("all-inclusive project price", text)
        self.assertNotIn("Unit Price", text)

    def test_many_items_generate_multiple_pages(self):
        reader, text = self.build(55, 85)
        self.assertGreater(len(reader.pages), 1)
        self.assertIn("DEMO-054", text)
        self.assertIn("Fictional material 84", text)

    def test_promotion_is_preserved(self):
        _, text = self.build(
            12, 2,
            "Cash Back promotion - fictional test only. "
            "Free Water Heater included when approved."
        )
        self.assertIn("Cash Back promotion", text)
        self.assertIn("Free Water Heater", text)
        self.assertIn("Promotional Offer", text)

    def test_no_overflow_returns_no_extra_document(self):
        reader, text = self.build(1, 0)
        self.assertIsNone(reader)
        self.assertEqual(text, "")

    def test_invalid_document_type_is_rejected(self):
        with self.assertRaises(ValueError):
            render_schedule_continuation(
                snapshot={
                    "equipment": [],
                    "materials": [],
                },
                project_code="TEST-1",
                document_kind="OTHER",
            )
