"""Real approved V4 PDF rendering tests; fictional business inputs only.

No ORM calls, database test setup, email, delivery, or issuance.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from pypdf import PdfReader

from .approved_final_receipt_reference_4756 import (
    REQUIRED_SURVEY_TEXT,
    verify_approved_final_receipt,
)
from .approved_receipt_overlay_preview_4223 import (
    AMOUNT_BASELINES,
    EQUIPMENT_COLUMNS,
)
from .final_receipt_adjudication_readiness_4789 import (
    FinalReceiptAdjudicationReadiness,
)
from .final_receipt_customer_candidate_4793 import (
    render_v4_receipt_customer_candidate,
)
from .final_receipt_financial_evidence_4760 import (
    FinalReceiptFinancialEvidence,
)


MODULE = "core.final_receipt_customer_candidate_4793"


class ActualV4DraftPDFTests4795(TestCase):
    def setUp(self):
        self.project_id = "11111111-1111-4111-8111-111111111111"
        self.msr_id = "22222222-2222-4222-8222-222222222222"

        self.snapshot = {
            "total_price": "1000.00",
            "customer_email": "fictional@example.invalid",
        }

        self.finances = FinalReceiptFinancialEvidence(
            project_id=self.project_id,
            approved_msr_id=self.msr_id,
            approved_msr_version=1,
            contract_total=Decimal("1000.00"),
            bank_confirmed_gross=Decimal("1000.00"),
            approved_adjustments=Decimal("0.00"),
            verified_customer_funds=Decimal("1000.00"),
            outstanding_balance=Decimal("0.00"),
            payment_fully_confirmed=True,
            overpayment_requires_review=False,
            installation_exception_present=False,
        )

        self.readiness = FinalReceiptAdjudicationReadiness(
            project_id=self.project_id,
            msr_id=self.msr_id,
            internal_receipt_verified=False,
            candidate_equipment_review_complete=True,
            provisional_ceo_adjudication_complete=True,
            expected_equipment_units=1,
            verified_ceo_approvals=1,
            blockers=("Customer issuance is not authorized.",),
        )

        self.customer = {
            "customer": "Fictional Sample Customer",
            "project_location": "123 Sample Street",
            "project_city": "Sampletown",
            "project_state": "MD",
            "project_zip": "21000",
            "customer_phone": "555-010-1000",
            "customer_email": "fictional@example.invalid",
        }

        self.projection = {
            key: "1000.00" for key in AMOUNT_BASELINES
        }
        self.projection["notes"] = ""

        self.rows = [
            {
                key: (
                    "Sample equipment" if key == "description" else ""
                )
                for key, _, _ in EQUIPMENT_COLUMNS
            }
            for _ in range(8)
        ]

        self.values = {
            "snapshot": self.snapshot,
            "project_id": self.project_id,
            "approved_msr_id": self.msr_id,
            "project_code": "FICTIONAL-4795",
            "invoice_number": "FICTIONAL-RECEIPT-4795",
            "invoice_date": date(2026, 11, 13),
            "finances": self.finances,
            "readiness": self.readiness,
        }

    def render(self, **changes):
        values = {**self.values, **changes}

        with (
            patch(
                MODULE + ".customer_document_data",
                return_value=self.customer,
            ),
            patch(
                MODULE + ".revised_invoice_projection",
                return_value=self.projection,
            ),
            patch(
                MODULE + ".project_equipment_rows",
                return_value=self.rows,
            ),
        ):
            return render_v4_receipt_customer_candidate(**values)

    def test_real_pdf_approved_reference_and_draft_markings(self):
        reference = verify_approved_final_receipt()
        result = self.render()

        self.assertEqual(result.status, "DRAFT_NOT_ISSUED")
        self.assertEqual(result.reference_sha256, reference.sha256)
        self.assertEqual(
            sha256(result.content).hexdigest(),
            result.pdf_sha256,
        )

        reader = PdfReader(BytesIO(result.content), strict=True)
        self.assertFalse(reader.is_encrypted)
        self.assertEqual(len(reader.pages), 1)

        page = reader.pages[0]
        self.assertEqual(
            (float(page.mediabox.width), float(page.mediabox.height)),
            (792.0, 612.0),
        )

        visible = page.extract_text() or ""

        for required in (
            "Fictional Sample Customer",
            "FICTIONAL-RECEIPT-4795",
            "DRAFT - NOT ISSUED",
            "DRAFT CUSTOMER COPY - NOT AUTHORIZED FOR ISSUANCE",
        ):
            self.assertIn(required, visible)

        self.assertNotIn("INTERNAL - NOT ISSUED", visible)

        metadata = reader.metadata
        self.assertIn(
            "draft, not issued",
            str(metadata.title).lower(),
        )

        for phrase in REQUIRED_SURVEY_TEXT:
            self.assertIn(phrase, visible)

        print(
            "PASS: Genuine approved V4 source renders one-page "
            "landscape draft."
        )
        print(
            "PASS: Draft watermark, survey, metadata, "
            "visible fields and PDF fingerprint verified."
        )

    def test_missing_or_incomplete_adjudication_denied(self):
        for change in (
            {"readiness": None},
            {
                "readiness": replace(
                    self.readiness,
                    provisional_ceo_adjudication_complete=False,
                )
            },
            {
                "readiness": replace(
                    self.readiness,
                    verified_ceo_approvals=0,
                )
            },
            {
                "readiness": replace(
                    self.readiness,
                    msr_id="FOREIGN-MSR",
                )
            },
        ):
            with self.subTest(change=str(change)):
                with self.assertRaises(ValueError):
                    self.render(**change)

        print("PASS: Missing and invalid adjudication rejected.")

    def test_false_authority_denied(self):
        for field in (
            "trusted_installation_evidence",
            "installation_authorized",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            with self.subTest(field=field):
                altered = replace(
                    self.readiness,
                    **{field: True},
                )
                with self.assertRaises(ValueError):
                    self.render(readiness=altered)

        print("PASS: False downstream authority rejected.")

    def test_financial_mismatch_and_overpayment_denied(self):
        with self.assertRaises(ValueError):
            self.render(
                finances=replace(
                    self.finances,
                    contract_total=Decimal("999.00"),
                )
            )

        with self.assertRaises(ValueError):
            self.render(
                finances=replace(
                    self.finances,
                    overpayment_requires_review=True,
                )
            )

        print("PASS: Price mismatch and overpayment rejected.")

    def test_pdf_integrity_detects_changed_bytes(self):
        result = self.render()

        self.assertNotEqual(
            sha256(result.content + b"TAMPER").hexdigest(),
            result.pdf_sha256,
        )

        self.assertTrue(result.content.startswith(b"%PDF-"))
        self.assertEqual(result.project_id, self.project_id)
        self.assertEqual(result.approved_msr_id, self.msr_id)
        self.assertEqual(result.status, "DRAFT_NOT_ISSUED")

        print("PASS: Exact output bytes and binding protected.")
