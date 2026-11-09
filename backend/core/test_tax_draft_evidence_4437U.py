"""Disposable Django tests for tax-draft evidence packaging."""
from copy import deepcopy
from uuid import uuid4
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import User, Role, Customer, Project, MSR, AuditEvent
from .tax_draft_evidence_4437U import prepare_tax_evidence_package, evidence_package_digest_matches

class TaxDraftEvidence4437UTests(TestCase):
    def setUp(self):
        self.comp = User.objects.create_user(username="tax_evidence_comp_4437u", password="fixture-only", role=Role.COMPTROLLER)
        self.ceo = User.objects.create_user(username="tax_evidence_ceo_4437u", password="fixture-only", role=Role.CEO)
        customer = Customer.objects.create(legal_name="Synthetic Customer", billing_address="Current Customer Address", created_by=self.comp)
        self.project = Project.objects.create(code="SYNTHETIC-TAX-4437U", customer=customer, location="Current Project Address", sales_associate=self.comp, reviewer=self.comp)
        self.msr = MSR.objects.create(project=self.project, number=2, status="APPROVED", snapshot={"customer":"Synthetic Customer", "financing_type":"NON_FINANCED", "billing_address":"Approved Billing DE", "project_location":"Approved Installation MD"}, created_by=self.comp, prepared_by=self.comp, approved_by=self.comp)
        Project.objects.filter(pk=self.project.pk).update(current_approved=self.msr)
        self.draft = dict(tax_year="2025", accounting_period="2026-10", jurisdiction="MARYLAND", tax_category="PROJECT_TAX_REVIEW", accounting_classification="OTHER_BUSINESS_TAX_EXPENSE", amount="125.00", source_reference="SYNTHETIC-SOURCE", evidence_reference="SYNTHETIC-DOCUMENT", explanation="Synthetic review only", filing_status="NOT_ESTABLISHED", project_related=True, project_id=str(self.project.pk), approved_msr_id=str(self.msr.pk), approved_msr_version=2)

    def test_01_package_is_fingerprinted(self):
        item = prepare_tax_evidence_package(self.comp, self.draft)
        self.assertTrue(evidence_package_digest_matches(item))
        self.assertEqual(len(item["sha256"]), 64)

    def test_02_approved_msr_snapshot_addresses_preserved(self):
        data = prepare_tax_evidence_package(self.comp, self.draft)["payload"]["captured_draft"]
        self.assertEqual(data["billing_address"], "Approved Billing DE")
        self.assertEqual(data["installation_address"], "Approved Installation MD")

    def test_03_exact_msr_version_and_identity_preserved(self):
        data = prepare_tax_evidence_package(self.comp, self.draft)["payload"]
        self.assertEqual(data["msr_version"], 2)
        self.assertEqual(data["msr_id"], str(self.msr.pk))
        self.assertEqual(data["project_id"], str(self.project.pk))

    def test_04_source_references_not_equated_with_verification(self):
        data = prepare_tax_evidence_package(self.comp, self.draft)["payload"]
        self.assertEqual(data["supporting_document_reference"], "SYNTHETIC-DOCUMENT")
        self.assertFalse(data["document_authenticity_verified"])
        self.assertFalse(data["independent_tax_entry_verified"])

    def test_05_all_operational_permissions_remain_false(self):
        data = prepare_tax_evidence_package(self.comp, self.draft)["payload"]
        for field in ("financial_report_eligible", "accounting_reconciled", "tax_posting_authorized", "tax_filing_authorized", "tax_payment_authorized"):
            with self.subTest(field=field):
                self.assertFalse(data[field])

    def test_06_tampering_changes_digest(self):
        item = prepare_tax_evidence_package(self.comp, self.draft)
        item["payload"]["captured_draft"]["amount"] = "999.00"
        self.assertFalse(evidence_package_digest_matches(item))

    def test_07_new_approved_msr_does_not_change_old_package(self):
        original = prepare_tax_evidence_package(self.comp, self.draft)
        newer = MSR.objects.create(project=self.project, number=3, status="APPROVED", snapshot={"customer":"Synthetic Customer", "financing_type":"NON_FINANCED", "billing_address":"New Billing DE", "project_location":"New Installation MD"}, created_by=self.comp, prepared_by=self.comp, approved_by=self.comp)
        Project.objects.filter(pk=self.project.pk).update(current_approved=newer)
        self.assertTrue(evidence_package_digest_matches(original))
        self.assertEqual(original["payload"]["captured_draft"]["installation_address"], "Approved Installation MD")
        with self.assertRaises(ValidationError):
            prepare_tax_evidence_package(self.comp, self.draft)

    def test_08_ceo_cannot_prepare_package(self):
        with self.assertRaises(PermissionDenied):
            prepare_tax_evidence_package(self.ceo, self.draft)

    def test_09_forged_msr_version_denied(self):
        with self.assertRaises(ValidationError):
            prepare_tax_evidence_package(self.comp, dict(self.draft, approved_msr_version=99))

    def test_10_forged_address_denied(self):
        with self.assertRaises(ValidationError):
            prepare_tax_evidence_package(self.comp, dict(self.draft, billing_address="FORGED"))

    def test_11_input_is_not_mutated(self):
        before = deepcopy(self.draft)
        prepare_tax_evidence_package(self.comp, self.draft)
        self.assertEqual(before, self.draft)

    def test_12_no_tax_record_or_audit_event_written(self):
        before = AuditEvent.objects.count()
        item = prepare_tax_evidence_package(self.comp, self.draft)
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertEqual(item["payload"]["status"], "UNVERIFIED_DRAFT_EVIDENCE_ONLY")

    def test_13_shared_snapshot_fingerprint(self):
        from .approved_document_msr_binding_4240 import (
            inspect_approved_msr_binding,
        )
        self.project.refresh_from_db()
        binding = inspect_approved_msr_binding(self.project, self.msr)
        package = prepare_tax_evidence_package(self.comp, self.draft)
        self.assertEqual(
            package["payload"]["msr_snapshot_sha256"],
            binding.snapshot_sha256,
        )
        self.assertTrue(evidence_package_digest_matches(package))

    def test_14_delivery_address_remains_unverified(self):
        draft = dict(
            self.draft, delivery_address="Synthetic delivery address"
        )
        package = prepare_tax_evidence_package(self.comp, draft)
        self.assertEqual(
            package["payload"]["delivery_address_source"],
            "UNVERIFIED_IF_SUPPLIED",
        )
        self.assertFalse(
            package["payload"]["document_authenticity_verified"]
        )

    def test_15_missing_delivery_address_is_explicit(self):
        package = prepare_tax_evidence_package(self.comp, self.draft)
        self.assertEqual(
            package["payload"]["delivery_address_source"],
            "NOT_PROVIDED",
        )
        self.assertTrue(evidence_package_digest_matches(package))

    def test_16_supplied_delivery_is_not_verified(self):
        draft = dict(
            self.draft,
            delivery_address="Synthetic separate delivery address",
        )
        package = prepare_tax_evidence_package(self.comp, draft)
        payload = package["payload"]
        self.assertEqual(
            payload["delivery_address_source"],
            "UNVERIFIED_IF_SUPPLIED",
        )
        self.assertEqual(
            payload["captured_draft"]["delivery_address"],
            "Synthetic separate delivery address",
        )
        self.assertFalse(payload["document_authenticity_verified"])
        self.assertFalse(payload["financial_report_eligible"])
