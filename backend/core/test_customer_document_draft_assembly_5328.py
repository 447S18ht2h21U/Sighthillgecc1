"""Focused, synthetic PDF draft assembly tests."""
from io import BytesIO

from django.test import SimpleTestCase
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from .customer_document_draft_assembly_5328 import (
    assemble_draft_document,
)


def first_page(marked=True):
    data = BytesIO()
    pen = canvas.Canvas(data, pagesize=(792, 612))
    pen.setFont("Helvetica-Bold", 15)
    pen.drawString(60, 500, "Fictional GECC Customer Invoice")
    if marked:
        pen.drawString(60, 450, "DRAFT - NOT ISSUED")
    pen.save()
    return data.getvalue()


def snapshot(equipment_count=12, material_count=12, promotion=True):
    result = {
        "customer": "Fictional Customer",
        "base_price": "12500.00",
        "discount": "0.00",
        "tax": "0.00",
        "total_price": "12500.00",
        "equipment": [
            {
                "brand": "Goodman",
                "residential_system_type": "Air conditioning",
                "model_number": f"DEMO-{i:03d}",
                "description": f"Fictional equipment {i}",
                "quantity": 1,
                "category_of_work": "Replacing existing equipment",
            }
            for i in range(equipment_count)
        ],
        "materials": [
            {"description": f"Fictional material {i}", "quantity": "2"}
            for i in range(material_count)
        ],
    }
    if promotion:
        result["other"] = {
            "type": "Cash Back",
            "notes": "Fictional customer receives Cash Back promotion.",
            "amount": "500.00",
        }
    return result


class DraftAssembly5328Tests(SimpleTestCase):
    def assemble(self, data):
        return assemble_draft_document(
            first_page_pdf=first_page(),
            snapshot=data,
            project_code="104-SA-2026-11-22",
            document_kind="RECEIPT",
        )

    def test_equipment_materials_and_promotion_survive(self):
        result = self.assemble(snapshot())
        pages = PdfReader(BytesIO(result["content"])).pages
        self.assertGreaterEqual(len(pages), 2)
        text = "\n".join(p.extract_text() or "" for p in pages)
        self.assertIn("DEMO-011", text)
        self.assertIn("Fictional material 11", text)
        self.assertIn("Cash Back promotion", text)
        self.assertTrue(all(
            "DRAFT - NOT ISSUED" in (p.extract_text() or "")
            for p in pages
        ))
        self.assertEqual(result["status"], "DRAFT_NOT_ISSUED")

    def test_large_schedule_preserves_final_entries(self):
        result = self.assemble(snapshot(55, 85, False))
        text = "\n".join(
            p.extract_text() or ""
            for p in PdfReader(BytesIO(result["content"])).pages
        )
        self.assertGreater(result["page_count"], 2)
        self.assertIn("DEMO-054", text)
        self.assertIn("Fictional material 84", text)

    def test_small_project_preserves_single_page(self):
        result = self.assemble(snapshot(1, 0, False))
        self.assertEqual(result["page_count"], 1)

    def test_unmarked_first_page_fails_closed(self):
        with self.assertRaises(ValueError):
            assemble_draft_document(
                first_page_pdf=first_page(False),
                snapshot=snapshot(),
                project_code="TEST",
                document_kind="INVOICE",
            )

    def test_inconsistent_project_price_fails_closed(self):
        data = snapshot()
        data["total_price"] = "12000.00"
        with self.assertRaises(ValueError):
            self.assemble(data)
