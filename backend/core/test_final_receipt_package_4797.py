"""Real equipment and V4 PDF package integration acceptance."""

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

from django.test import TestCase, override_settings

from . import test_equipment_full_chain_4788 as foundation
from .test_final_receipt_actual_pdf_4795 import ActualV4DraftPDFTests4795
from .final_equipment_addendum_4796 import (
    render_equipment_addendum_draft,
)
from .final_receipt_package_4797 import build_receipt_package_draft
from .models import Document, ReceiptDispatchOutbox


@override_settings(DEBUG=True, ENVIRONMENT="development")
class PairedDraftAcceptance4797(TestCase):
    setUp = foundation.FullEquipmentEvidenceChain4788.setUp
    prepare_real_evidence = (
        foundation.FullEquipmentEvidenceChain4788.prepare_real_evidence
    )
    decide = foundation.FullEquipmentEvidenceChain4788.decide

    def prepare_pair(self):
        manifest = self.prepare_real_evidence()

        for unit in manifest.reviewed_units:
            self.decide(unit.unit_id)

        addendum = render_equipment_addendum_draft(self.project)

        pdf_fixture = ActualV4DraftPDFTests4795()
        pdf_fixture.setUp()

        total = Decimal(str(self.msr.snapshot["total_price"]))

        pdf_fixture.project_id = str(self.project.pk)
        pdf_fixture.msr_id = str(self.msr.pk)
        pdf_fixture.snapshot = self.msr.snapshot
        pdf_fixture.finances = replace(
            pdf_fixture.finances,
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version=self.msr.number,
            contract_total=total,
            bank_confirmed_gross=total,
            verified_customer_funds=total,
        )
        pdf_fixture.readiness = replace(
            pdf_fixture.readiness,
            project_id=str(self.project.pk),
            msr_id=str(self.msr.pk),
            expected_equipment_units=len(manifest.reviewed_units),
            verified_ceo_approvals=len(manifest.reviewed_units),
        )
        pdf_fixture.values.update(
            snapshot=pdf_fixture.snapshot,
            project_id=pdf_fixture.project_id,
            approved_msr_id=pdf_fixture.msr_id,
            project_code=str(self.project.code),
            finances=pdf_fixture.finances,
            readiness=pdf_fixture.readiness,
        )

        receipt = pdf_fixture.render()
        return receipt, addendum, manifest

    def test_real_paired_package_is_draft_only(self):
        receipt, addendum, manifest = self.prepare_pair()

        result = build_receipt_package_draft(
            project=self.project,
            receipt=receipt,
            addendum=addendum,
        )

        self.assertEqual(result.status, "DRAFT_NOT_ISSUED")
        self.assertFalse(result.issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertEqual(
            sha256(result.archive).hexdigest(),
            result.archive_sha256,
        )

        with ZipFile(BytesIO(result.archive)) as archive:
            self.assertEqual(len(archive.namelist()), 3)
            self.assertIn(
                b"DRAFT",
                archive.read("draft-manifest.json"),
            )

        self.assertEqual(
            addendum.equipment_count,
            len(manifest.reviewed_units),
        )
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 0)

        print("PASS: Real draft Receipt and serial addendum paired.")
        print("PASS: ZIP fingerprints and MSR identity verified.")
        print("PASS: No document issuance or dispatch records created.")

    def test_cross_msr_package_rejected(self):
        receipt, addendum, _ = self.prepare_pair()

        with self.assertRaises(ValueError):
            build_receipt_package_draft(
                project=self.project,
                receipt=replace(
                    receipt,
                    approved_msr_id="FOREIGN-MSR",
                ),
                addendum=addendum,
            )

        with self.assertRaises(ValueError):
            build_receipt_package_draft(
                project=self.project,
                receipt=receipt,
                addendum=replace(
                    addendum,
                    snapshot_sha256="0" * 64,
                ),
            )

        print("PASS: Cross-MSR and snapshot substitutions rejected.")

    def test_pdf_substitution_and_false_authority_rejected(self):
        receipt, addendum, _ = self.prepare_pair()

        for changed in (
            replace(receipt, content=receipt.content + b"TAMPER"),
            replace(receipt, status="FINAL"),
        ):
            with self.assertRaises(ValueError):
                build_receipt_package_draft(
                    project=self.project,
                    receipt=changed,
                    addendum=addendum,
                )

        with self.assertRaises(ValueError):
            build_receipt_package_draft(
                project=self.project,
                receipt=receipt,
                addendum=replace(
                    addendum,
                    customer_issuance_authorized=True,
                ),
            )

        print("PASS: Changed PDF and false issuance claims rejected.")
