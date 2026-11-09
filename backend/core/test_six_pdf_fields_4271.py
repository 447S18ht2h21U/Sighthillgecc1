"""Batched field-level acceptance of real fictional six-document PDFs.

No operational signing, delivery, release, or database changes.
"""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re

from django.test import TestCase
from pypdf import PdfReader

from .approved_document_lifecycle_4248 import LifecycleDenied
from .approved_document_lifecycle_integration_4249 import (
    inspect_integrated_document_lifecycle,
)
from .approved_document_version_lock_4250 import (
    inspect_version_locked_review,
)
from .approved_six_document_batch_4236 import KINDS
from .models import Document
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class SixPDFFieldAcceptance4271Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)
        self.original = deepcopy(self.full_msr.snapshot)
        self.batch = RealLifecycleIntegration4249Tests.render(self)

        self.assertEqual(set(self.batch["pdfs"]), set(KINDS))
        self.assertTrue(self.batch["review_only"])
        self.assertFalse(self.batch["release_authorized"])

        self.readers = {}
        self.text = {}

        for kind, payload in self.batch["pdfs"].items():
            self.assertIsInstance(payload, bytes)
            self.assertTrue(payload.startswith(b"%PDF-"))
            reader = PdfReader(BytesIO(payload), strict=True)
            self.assertGreater(len(reader.pages), 0)
            self.readers[kind] = reader

            words = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            fields = reader.get_fields() or {}
            for name, field in fields.items():
                words += "\n" + str(name)
                value = field.get("/V") if hasattr(field, "get") else None
                if value is not None:
                    words += "\n" + str(value)

            self.text[kind] = " ".join(words.split())

    def assert_printed(self, kind, field, value):
        self.assertTrue(
            isinstance(value, str) and bool(value.strip()),
            f"{kind}: source field {field} is empty.",
        )
        expected = " ".join(value.split()).casefold()
        actual = self.text[kind].casefold()
        self.assertIn(
            expected,
            actual,
            f"{kind}: approved MSR {field} not found in PDF text.",
        )

    def test_01_customer_and_addresses_on_all_six(self):
        snapshot = self.original
        fields = (
            "customer",
            "billing_address",
            "project_location",
        )
        for kind in KINDS:
            with self.subTest(document=kind, field="project_code"):
                self.assert_printed(
                    kind, "project_code", self.project.code
                )
            for field in fields:
                with self.subTest(document=kind, field=field):
                    self.assert_printed(
                        kind, field, snapshot.get(field, "")
                    )
        print("PASS: Customer, project, and both addresses on all six PDFs.")

    def test_02_equipment_model_on_applicable_documents(self):
        equipment = self.original.get("equipment", [])
        models = [
            item["model_number"]
            for item in equipment
            if isinstance(item, dict)
            and isinstance(item.get("model_number"), str)
            and item["model_number"].strip()
        ]
        self.assertGreater(len(models), 0)

        for kind in ("CUSTOMER_SOW", "INVOICE", "RECEIPT"):
            for model in models:
                with self.subTest(document=kind, model=model):
                    self.assert_printed(kind, "equipment_model", model)

        print("PASS: All listed equipment models in SOW, Invoice, Receipt.")

    def test_03_invoice_number_and_document_distinction(self):
        number = "FICTIONAL-INVOICE-4245"
        for kind in ("INVOICE", "RECEIPT"):
            with self.subTest(document=kind):
                self.assert_printed(kind, "invoice_number", number)

        hashes = {
            kind: sha256(self.batch["pdfs"][kind]).hexdigest()
            for kind in KINDS
        }
        self.assertEqual(len(set(hashes.values())), len(KINDS))
        self.assertEqual(len(self.readers), 6)

        print("PASS: Invoice identifier and six distinct valid documents.")

    def test_04_commercial_total_in_customer_price_documents(self):
        raw = self.original.get("total_price")
        self.assertIsNotNone(raw)
        amount = Decimal(str(raw))
        self.assertTrue(amount.is_finite())
        self.assertGreaterEqual(amount, 0)

        plain = f"{amount:.2f}"
        grouped = f"{amount:,.2f}"

        variants = (
            plain, grouped, "$" + plain, "$" + grouped,
            "$ " + plain, "$ " + grouped,
        )

        for kind in ("CUSTOMER_SOW", "INVOICE", "RECEIPT"):
            with self.subTest(document=kind, field="total_price"):
                text = self.text[kind]
                matched = any(
                    re.search(
                        r"(?<![\d.,])" + re.escape(variant) + r"(?![\d.,])",
                        text,
                    )
                    for variant in variants
                )
                self.assertTrue(
                    matched,
                    f"{kind}: approved total_price not found as an "
                    "exact decimal, grouped amount, or currency amount. "
                    "Review actual PDF commercial mapping.",
                )

        print("PASS: Approved total price in SOW, Invoice, and Receipt.")

    def test_05_version_integrity_and_no_operational_promotion(self):
        self.project.refresh_from_db()
        self.assertEqual(
            self.project.current_approved_id, self.full_msr.pk
        )
        self.assertEqual(self.full_msr.status, "APPROVED")
        self.assertEqual(self.full_msr.number, 3)

        report = inspect_version_locked_review(
            project=self.project,
            msr=self.full_msr,
            batch=self.batch,
        )
        self.assertEqual(len(report.documents), 6)
        self.assertTrue(
            all(item.preview_verified for item in report.documents)
        )
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.project_completion_authorized)
        self.assertTrue(all(
            not item.signed_evidence_verified
            and not item.customer_delivery_verified
            and not item.completion_evidence_verified
            for item in report.documents
        ))

        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, self.original)
        self.assertEqual(Document.objects.count(), 0)

        corrupted = {
            **self.batch,
            "pdfs": dict(self.batch["pdfs"]),
        }
        corrupted["pdfs"]["INVOICE"] += b"unauthorized-change"
        with self.assertRaises(LifecycleDenied):
            inspect_integrated_document_lifecycle(corrupted)

        print("PASS: Approved version immutable, tampering denied.")
        print("PASS: No signature, delivery, installation, or completion.")