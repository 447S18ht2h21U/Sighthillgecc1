"""Real equipment-chain PDF acceptance, disposable SQLite only."""

from hashlib import sha256
from io import BytesIO

from django.test import TestCase, override_settings
from pypdf import PdfReader

from . import test_equipment_full_chain_4788 as foundation
from .final_equipment_addendum_4796 import (
    render_equipment_addendum_draft,
)
from .models import Document, ReceiptDispatchOutbox


@override_settings(DEBUG=True, ENVIRONMENT="development")
class EquipmentAddendumAcceptance4796(TestCase):
    setUp = foundation.FullEquipmentEvidenceChain4788.setUp
    prepare_real_evidence = (
        foundation.FullEquipmentEvidenceChain4788.prepare_real_evidence
    )
    decide = foundation.FullEquipmentEvidenceChain4788.decide

    def test_full_chain_generates_serial_addendum(self):
        manifest = self.prepare_real_evidence()

        for unit in manifest.reviewed_units:
            self.decide(unit.unit_id)

        result = render_equipment_addendum_draft(self.project)

        self.assertEqual(result.status, "DRAFT_NOT_ISSUED")
        self.assertEqual(
            result.equipment_count, len(manifest.reviewed_units)
        )
        self.assertEqual(
            sha256(result.content).hexdigest(), result.pdf_sha256
        )

        reader = PdfReader(BytesIO(result.content), strict=True)
        visible = "\n".join(
            page.extract_text() or "" for page in reader.pages
        )

        for unit in manifest.reviewed_units:
            self.assertIn(unit.unit_id, visible)
            self.assertIn(unit.serial_number, visible)

        self.assertIn("DRAFT - NOT ISSUED", visible)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.customer_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 0)

        print("PASS: Actual serial numbers rendered in draft PDF.")
        print("PASS: Immutable project and MSR identity preserved.")
        print("PASS: No issued Document or dispatch intent created.")

    def test_missing_ceo_decision_prevents_rendering(self):
        manifest = self.prepare_real_evidence()
        self.assertTrue(manifest.all_candidates_reviewed)

        with self.assertRaises(ValueError):
            render_equipment_addendum_draft(self.project)

        print("PASS: Review alone cannot generate addendum.")

    def test_rejected_ceo_decision_prevents_rendering(self):
        manifest = self.prepare_real_evidence()

        for index, unit in enumerate(manifest.reviewed_units):
            self.decide(unit.unit_id, approve=(index != 0))

        with self.assertRaises(ValueError):
            render_equipment_addendum_draft(self.project)

        print("PASS: Rejected adjudication blocks addendum.")

    def test_rejected_inspection_prevents_rendering(self):
        self.prepare_real_evidence(
            reject_unit=self.units[0].unit_id
        )

        with self.assertRaises(ValueError):
            render_equipment_addendum_draft(self.project)

        print("PASS: Rejected physical inspection blocks addendum.")
