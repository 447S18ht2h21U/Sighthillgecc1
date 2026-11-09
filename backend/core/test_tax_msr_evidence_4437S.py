"""Isolated Django MSR-to-tax security integration tests."""
from copy import deepcopy
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import User, Role, Customer, Project, MSR
from .tax_msr_evidence_4437S import bind_project_tax_draft

class TaxMSREvidence4437STests(TestCase):
    def setUp(self):
        self.comp = User.objects.create_user(username="msr_tax_comp_4437s", password="fixture-only", role=Role.COMPTROLLER)
        self.ceo = User.objects.create_user(username="msr_tax_ceo_4437s", password="fixture-only", role=Role.CEO)
        self.customer = Customer.objects.create(legal_name="Fictional Customer", billing_address="Customer current address", created_by=self.comp)
        self.project = Project.objects.create(code="FICTIONAL-TAX-4437S-01", customer=self.customer, location="Project current location", sales_associate=self.comp, reviewer=self.comp)
        self.msr = MSR.objects.create(project=self.project, number=2, status="APPROVED", snapshot={"customer":"Fictional Customer", "financing_type":"NON_FINANCED", "billing_address":"Approved billing DE", "project_location":"Approved site MD"}, created_by=self.comp, prepared_by=self.comp, approved_by=self.comp)
        Project.objects.filter(pk=self.project.pk).update(current_approved=self.msr)
        self.entry = dict(tax_year="2025", accounting_period="2026-10", jurisdiction="MARYLAND", tax_category="PROJECT_TAX_REVIEW", accounting_classification="OTHER_BUSINESS_TAX_EXPENSE", amount="125.00", source_reference="FICTIONAL-SOURCE", evidence_reference="FICTIONAL-EVIDENCE", explanation="FICTIONAL REVIEW", filing_status="NOT_ESTABLISHED", project_related=True, project_id=str(self.project.pk), approved_msr_id=str(self.msr.pk), approved_msr_version=2)

    def test_01_approved_snapshot_bound(self):
        result = bind_project_tax_draft(self.comp, self.entry)
        self.assertEqual(result["billing_address"], "Approved billing DE")
        self.assertEqual(result["installation_address"], "Approved site MD")
        self.assertFalse(result["eligible_for_financial_reporting"])

    def test_02_current_customer_address_not_substituted(self):
        result = bind_project_tax_draft(self.comp, self.entry)
        self.assertNotEqual(result["billing_address"], self.customer.billing_address)

    def test_03_current_project_location_not_substituted(self):
        result = bind_project_tax_draft(self.comp, self.entry)
        self.assertNotEqual(result["installation_address"], self.project.location)

    def test_04_wrong_version_denied(self):
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, approved_msr_version=1))

    def test_05_wrong_msr_identifier_denied(self):
        from uuid import uuid4
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, approved_msr_id=str(uuid4())))

    def test_06_forged_billing_address_denied(self):
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, billing_address="FORGED"))

    def test_07_forged_installation_address_denied(self):
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, installation_address="FORGED"))

    def test_08_unapproved_msr_denied(self):
        draft = MSR.objects.create(project=self.project, number=3, status="DRAFT", snapshot={"billing_address":"Approved billing DE", "project_location":"Approved site MD"}, created_by=self.comp, prepared_by=self.comp); Project.objects.filter(pk=self.project.pk).update(current_approved=draft)
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, approved_msr_id=str(draft.pk), approved_msr_version=3))

    def test_09_missing_current_approved_denied(self):
        Project.objects.filter(pk=self.project.pk).update(current_approved=None)
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, self.entry)

    def test_10_ceo_cannot_prepare(self):
        with self.assertRaises(PermissionDenied):
            bind_project_tax_draft(self.ceo, self.entry)

    def test_11_incomplete_msr_snapshot_denied(self):
        incomplete = MSR.objects.create(project=self.project, number=3, status="APPROVED", snapshot={"billing_address":"Approved billing DE"}, created_by=self.comp, prepared_by=self.comp, approved_by=self.comp); Project.objects.filter(pk=self.project.pk).update(current_approved=incomplete)
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, approved_msr_id=str(incomplete.pk), approved_msr_version=3))

    def test_12_original_draft_unchanged(self):
        before = deepcopy(self.entry)
        result = bind_project_tax_draft(self.comp, self.entry)
        result["billing_address"] = "TAMPERED RETURN VALUE"
        self.assertEqual(self.entry, before)

    def test_13_invalid_project_id_denied(self):
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, project_id="INVALID"))

    def test_14_cross_project_msr_denied(self):
        second = Project.objects.create(code="FICTIONAL-TAX-4437S-02", customer=self.customer, location="Other site", sales_associate=self.comp, reviewer=self.comp)
        other = MSR.objects.create(project=second, number=2, status="APPROVED", snapshot={"billing_address":"Other billing", "project_location":"Other site"}, created_by=self.comp, prepared_by=self.comp, approved_by=self.comp)
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, dict(self.entry, approved_msr_id=str(other.pk)))

    def test_15_cancelled_project_denied(self):
        Project.objects.filter(pk=self.project.pk).update(state="CANCELLED")
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, self.entry)

    def test_16_missing_financing_classification_denied(self):
        malformed = MSR.objects.create(
            project=self.project, number=3, status="APPROVED",
            snapshot={
                "customer": "Fictional Customer",
                "billing_address": "Approved billing DE",
                "project_location": "Approved site MD",
            },
            created_by=self.comp, prepared_by=self.comp,
            approved_by=self.comp,
        )
        Project.objects.filter(pk=self.project.pk).update(
            current_approved=malformed
        )
        bad = dict(
            self.entry,
            approved_msr_id=str(malformed.pk),
            approved_msr_version=3,
        )
        with self.assertRaises(ValidationError):
            bind_project_tax_draft(self.comp, bad)
