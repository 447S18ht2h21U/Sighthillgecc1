"""Real equipment, adjudication, Document and Receipt boundary integration.

The upstream financial/equipment preflight assessment is substituted.
No real provider, customer issuance, or trusted installation promotion.
"""

import hashlib
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from reportlab.pdfgen import canvas

from . import test_equipment_full_chain_4788 as foundation
from .documents import canonical_hash
from .final_receipt_adjudication_readiness_4789 import (
    assess_final_receipt_adjudication_readiness,
)
from .final_receipt_internal_retention_4770 import RENDERER_VERSION
from .models import Document, ReceiptDispatchOutbox
from .receipt_equipment_manifest_4768 import (
    build_receipt_equipment_manifest,
)


BOUNDARY = "core.final_receipt_issuance_boundary_4781"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealEquipmentReceiptIntegration4790(TestCase):
    setUp = foundation.FullEquipmentEvidenceChain4788.setUp
    prepare_real_evidence = (
        foundation.FullEquipmentEvidenceChain4788.prepare_real_evidence
    )
    decide = foundation.FullEquipmentEvidenceChain4788.decide

    def gate(self, manifest):
        return SimpleNamespace(
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            trusted_equipment_evidence=False,
            retention_authorized=False,
            final_receipt_verified=False,
            customer_delivery_verified=False,
            completion_authorized=False,
            candidate_evidence_complete=(
                manifest.all_candidates_reviewed
            ),
            blockers=(
                "Real customer Receipt issuance remains blocked.",
            ),
        )

    def evaluate(self, manifest):
        # The real boundary reads actual Document and outbox tables.
        # Only the upstream preflight result is a test fixture.
        with patch(
            BOUNDARY + ".assess_final_receipt_evidence_gate",
            return_value=self.gate(manifest),
        ):
            return assess_final_receipt_adjudication_readiness(
                self.project
            )

    def internal_document(self):
        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=(792, 612))
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(90, 405, "INTERNAL - NOT ISSUED")
        pdf.showPage()
        pdf.save()

        content = output.getvalue()
        reference = "a" * 64

        return Document.objects.create(
            msr=self.msr,
            kind=Document.Kind.RECEIPT,
            created_by=self.comptroller,
            status="PREPARATION",
            filename="FICTIONAL-4790-INTERNAL.pdf",
            template_sha256=reference,
            snapshot_sha256=canonical_hash(self.msr.snapshot),
            pdf_sha256=hashlib.sha256(content).hexdigest(),
            renderer_version=RENDERER_VERSION,
            values={
                "purpose": "INTERNAL_NOT_ISSUED",
                "project_id": str(self.project.pk),
                "msr_id": str(self.msr.pk),
                "msr_version": self.msr.number,
                "reference_sha256": reference,
                "customer_delivery_verified": False,
                "completion_authorized": False,
            },
            content=content,
        )

    def assert_never_authorized(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertTrue(result.blockers)

    def test_complete_chain_with_real_internal_document(self):
        manifest = self.prepare_real_evidence()
        self.assertTrue(manifest.all_candidates_reviewed)

        for unit in manifest.reviewed_units:
            self.decide(unit.unit_id)

        document = self.internal_document()
        result = self.evaluate(manifest)

        self.assertTrue(result.internal_receipt_verified)
        self.assertTrue(
            result.provisional_ceo_adjudication_complete
        )
        self.assertEqual(
            result.verified_ceo_approvals,
            len(manifest.reviewed_units),
        )
        self.assert_never_authorized(result)

        self.assertEqual(
            Document.objects.get(pk=document.pk).status,
            "PREPARATION",
        )
        self.assertEqual(
            ReceiptDispatchOutbox.objects.count(), 0
        )

        print(
            "PASS: Real equipment, CEO decisions, internal PDF "
            "and issuance boundary integrated."
        )
        print("PASS: Complete adjudication cannot issue Receipt.")

    def test_missing_ceo_decision_remains_blocked(self):
        manifest = self.prepare_real_evidence()
        self.internal_document()

        result = self.evaluate(manifest)

        self.assertTrue(result.internal_receipt_verified)
        self.assertFalse(
            result.provisional_ceo_adjudication_complete
        )
        self.assert_never_authorized(result)

        print(
            "PASS: Real retained PDF does not override "
            "missing CEO adjudication."
        )

    def test_rejected_decision_remains_blocked(self):
        manifest = self.prepare_real_evidence()

        for index, unit in enumerate(manifest.reviewed_units):
            self.decide(
                unit.unit_id,
                approve=(index != 0),
            )

        self.internal_document()
        result = self.evaluate(manifest)

        self.assertFalse(
            result.provisional_ceo_adjudication_complete
        )
        self.assert_never_authorized(result)

        print(
            "PASS: Rejected decision and internal PDF "
            "cannot authorize issuance."
        )

    def test_missing_internal_document_remains_blocked(self):
        manifest = self.prepare_real_evidence()

        for unit in manifest.reviewed_units:
            self.decide(unit.unit_id)

        result = self.evaluate(manifest)

        self.assertFalse(result.internal_receipt_verified)
        self.assertTrue(
            result.provisional_ceo_adjudication_complete
        )
        self.assert_never_authorized(result)
        self.assertEqual(Document.objects.count(), 0)

        print(
            "PASS: Complete equipment chain without "
            "retained PDF remains blocked."
        )
