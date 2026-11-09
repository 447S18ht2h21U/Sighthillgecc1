"""Real Django records to six actual approved PDFs, development only."""
import os
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from .approved_document_record_bridge_4244 import (
    prepare_fictional_document_review,
)
from .approved_six_document_batch_4236 import KINDS
from .models import Document, MSR
from .test_approved_document_real_db_4243 import (
    RealDocumentRecord4243Tests,
)
from .test_approved_sow_page_two_4232 import SOWPageTwo4232Tests


class RealRecordSixPDF4245Tests(TestCase):
    def setUp(self):
        if (
            settings.DATABASES["default"]["ENGINE"]
            != "django.db.backends.sqlite3"
            or settings.DATABASES["default"].get("TEST", {}).get("NAME")
            != ":memory:"
        ):
            raise RuntimeError("Disposable SQLite test settings required.")

        RealDocumentRecord4243Tests.setUp(self)

        source = SOWPageTwo4232Tests()
        source.setUp()
        self.full_snapshot = deepcopy(source.snapshot)
        self.reference = Path(
            os.environ["VERIDIAN_APPROVED_PDF_REFERENCE_DIR"]
        )

        # Create a proper new approved version in the isolated database.
        # Do not modify the earlier approved MSR.
        self.full_msr = MSR.objects.create(
            project=self.project,
            number=2,
            status="DRAFT",
            source=self.msr,
            created_by=self.associate,
            prepared_by=self.associate,
            snapshot=deepcopy(self.full_snapshot),
        )
        self.full_msr.status = "APPROVED"
        self.full_msr.approved_by = self.comptroller
        self.full_msr.save(update_fields=["status", "approved_by"])
        self.project.current_approved = self.full_msr
        self.project.save(update_fields=["current_approved"])

    def render(self):
        with patch.dict(os.environ, {
            "VERIDIAN_APPROVED_PDF_PREVIEW_GATE": "enabled-test-only",
            "VERIDIAN_ENVIRONMENT": "development",
            "GECC_DEV": "1",
        }):
            return prepare_fictional_document_review(
                actor=self.comptroller,
                project=self.project,
                msr=self.full_msr,
                directory=self.reference,
                created="2026-11-04",
                associate="FICTIONAL ASSOCIATE",
                invoice_number="FICTIONAL-INVOICE-4245",
                invoice_date="2026-11-04",
            )

    def test_real_records_render_all_six_actual_pdfs(self):
        # A no-promotion scenario is permitted; the zero discount
        # field must remain present and the financial total adjusted.
        snapshot = deepcopy(self.full_snapshot)
        promotion = snapshot.pop("other")
        self.assertEqual(promotion["type"], "Reduced Price")
        self.assertEqual(
            Decimal(str(snapshot["discount"])), Decimal("150.00")
        )
        snapshot["discount"] = "0.00"
        snapshot["total_price"] = str(
            Decimal(str(snapshot["total_price"])) + Decimal("150.00")
        )

        # A separate approved test-only version, not an update of
        # the existing immutable approved MSR.
        plain = MSR.objects.create(
            project=self.project,
            number=3,
            status="DRAFT",
            source=self.full_msr,
            created_by=self.associate,
            prepared_by=self.associate,
            snapshot=snapshot,
        )
        plain.status = "APPROVED"
        plain.approved_by = self.comptroller
        plain.save(update_fields=["status", "approved_by"])
        self.project.current_approved = plain
        self.project.save(update_fields=["current_approved"])
        self.full_msr = plain

        original = deepcopy(plain.snapshot)
        batch = self.render()

        self.assertEqual(
            tuple(item["kind"] for item in batch["manifest"]), KINDS
        )
        self.assertEqual(len(batch["pdfs"]), 6)
        self.assertTrue(all(batch["pdfs"][kind] for kind in KINDS))
        self.assertTrue(batch["review_only"])
        self.assertFalse(batch["release_authorized"])
        self.assertEqual(batch["record"].msr_id, str(plain.pk))
        self.assertEqual(batch["record"].version, 3)
        self.assertEqual(Document.objects.count(), 0)

        plain.refresh_from_db()
        self.assertEqual(plain.snapshot, original)
        print("PASS: Six real PDFs from approved fictional DB record.")

    def test_promotion_requires_receipt_disclosure(self):
        original = deepcopy(self.full_msr.snapshot)
        with self.assertRaisesRegex(
            ValueError,
            "Promotion details require an approved Receipt disclosure",
        ):
            self.render()

        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, original)
        self.assertEqual(Document.objects.count(), 0)
        print("PASS: Undisclosed promotion blocked.")