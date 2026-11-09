"""Test-only readable-content inventory of six real fictional PDF previews."""
from copy import deepcopy
from io import BytesIO

from django.test import TestCase
from pypdf import PdfReader

from .approved_six_document_batch_4236 import KINDS
from .models import Document
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class MockCustomerPDFContent4270Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def test_actual_six_pdf_readability_and_value_inventory(self):
        original = deepcopy(self.full_msr.snapshot)
        batch = RealLifecycleIntegration4249Tests.render(self)

        self.assertEqual(set(batch["pdfs"]), set(KINDS))
        self.assertTrue(batch["review_only"])
        self.assertFalse(batch["release_authorized"])

        snapshot = self.full_msr.snapshot
        markers = {
            "customer": snapshot.get("customer", ""),
            "project_code": self.project.code,
            "billing_address": snapshot.get("billing_address", ""),
            "project_location": snapshot.get("project_location", ""),
            "total_price": str(snapshot.get("total_price", "")),
            "invoice_number": "FICTIONAL-INVOICE-4245",
        }

        equipment = snapshot.get("equipment", [])
        for item in equipment[:2]:
            if isinstance(item, dict):
                model = item.get("model_number")
                if isinstance(model, str) and model.strip():
                    markers["equipment_model"] = model
                    break

        self.assertIn("FICTIONAL", markers["customer"].upper())

        print("\n=== ACTUAL GENERATED PDF CONTENT COVERAGE ===")
        print("YES = extracted text or a PDF form-field value contains the MSR value")
        print("NO = value was not found by these two extraction methods")
        print("N/A = no usable source value was supplied")
        print("A NO result is a finding to investigate, not an automatic mapping failure.")

        coverage = {}
        for kind in KINDS:
            payload = batch["pdfs"][kind]
            self.assertIsInstance(payload, bytes)
            self.assertTrue(
                payload.startswith(b"%PDF-"),
                f"{kind} is missing a PDF header.",
            )

            reader = PdfReader(BytesIO(payload), strict=True)
            self.assertGreater(
                len(reader.pages), 0,
                f"{kind} has no readable PDF pages.",
            )

            page_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )

            fields = reader.get_fields() or {}
            form_values = []
            for key, field in fields.items():
                form_values.append(str(key))
                value = field.get("/V") if hasattr(field, "get") else None
                if value is not None:
                    form_values.append(str(value))

            visible = page_text + "\n" + "\n".join(form_values)
            collapsed = " ".join(visible.split()).casefold()

            coverage[kind] = {}
            print(
                f"\n{kind}: pages={len(reader.pages)} "
                f"bytes={len(payload)} fields={len(fields)}"
            )

            for label, value in markers.items():
                if not isinstance(value, str) or not value.strip():
                    result = "N/A"
                else:
                    result = (
                        "YES"
                        if " ".join(value.split()).casefold() in collapsed
                        else "NO"
                    )
                coverage[kind][label] = result
                print(f"  {label}: {result}")

        print("\n=== DOCUMENTS WITH EACH SOURCE VALUE ===")
        for label in markers:
            matched = [
                kind for kind in KINDS
                if coverage[kind][label] == "YES"
            ]
            print(f"{label}: {', '.join(matched) if matched else 'NONE'}")

        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, original)
        self.assertEqual(Document.objects.count(), 0)

        print("\nPASS: All six generated PDFs parsed successfully.")
        print("PASS: Approved MSR snapshot remained unchanged.")
        print("PASS: No operational Document records were created.")
        print("NOTE: Field-by-field assertions require review of this inventory.")