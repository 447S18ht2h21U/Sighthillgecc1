"""Isolated tests of CEO tax-verification readiness, not actual approval."""
from copy import deepcopy

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, Customer, MSR, Project, Role, User
from .tax_draft_evidence_4437U import prepare_tax_evidence_package
from .tax_ceo_verification_review_4438L import (
    review_ceo_tax_verification_candidate,
)


class CEOTaxVerificationReview4438LTests(TestCase):
    def setUp(self):
        self.comp = User.objects.create_user(
            username="tax_verify_comp_4438l",
            password="fixture-only",
            role=Role.COMPTROLLER,
        )
        self.ceo = User.objects.create_user(
            username="tax_verify_ceo_4438l",
            password="fixture-only",
            role=Role.CEO,
        )
        customer = Customer.objects.create(
            legal_name="Synthetic Tax Customer",
            billing_address="Current customer address",
            created_by=self.comp,
        )
        project = Project.objects.create(
            code="SYNTHETIC-TAX-4438L",
            customer=customer,
            location="Current installation address",
            sales_associate=self.comp,
            reviewer=self.comp,
        )
        msr = MSR.objects.create(
            project=project,
            number=2,
            status="APPROVED",
            snapshot={
                "customer": "Synthetic Tax Customer",
                "financing_type": "NON_FINANCED",
                "billing_address": "Approved billing address",
                "project_location": "Approved installation address",
            },
            created_by=self.comp,
            prepared_by=self.comp,
            approved_by=self.comp,
        )
        Project.objects.filter(pk=project.pk).update(
            current_approved=msr
        )
        draft = dict(
            tax_year="2025",
            accounting_period="2026-10",
            jurisdiction="MARYLAND",
            tax_category="PROJECT_TAX_REVIEW",
            accounting_classification="OTHER_BUSINESS_TAX_EXPENSE",
            amount="125.00",
            source_reference="SYNTHETIC-SOURCE",
            evidence_reference="SYNTHETIC-DOCUMENT",
            explanation="Synthetic review only",
            filing_status="NOT_ESTABLISHED",
            project_related=True,
            project_id=str(project.pk),
            approved_msr_id=str(msr.pk),
            approved_msr_version=2,
        )
        self.package = prepare_tax_evidence_package(self.comp, draft)

    def test_01_ceo_can_inspect_but_cannot_verify(self):
        result = review_ceo_tax_verification_candidate(
            self.ceo, self.package
        )
        self.assertEqual(result["status"], "PRELIMINARY_REVIEW_ONLY")
        self.assertFalse(result["verification_authorized"])
        self.assertFalse(result["independent_tax_entry_verified"])

    def test_02_comptroller_cannot_verify_own_draft(self):
        with self.assertRaises(PermissionDenied):
            review_ceo_tax_verification_candidate(
                self.comp, self.package
            )

    def test_03_inactive_ceo_denied(self):
        self.ceo.is_active = False
        self.ceo.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            review_ceo_tax_verification_candidate(
                self.ceo, self.package
            )

    def test_04_stale_cached_ceo_role_denied(self):
        User.objects.filter(pk=self.ceo.pk).update(
            role=Role.SALES_MANAGER
        )
        with self.assertRaises(PermissionDenied):
            review_ceo_tax_verification_candidate(
                self.ceo, self.package
            )

    def test_05_changed_evidence_denied(self):
        altered = deepcopy(self.package)
        altered["payload"]["captured_draft"]["amount"] = "9999.00"
        with self.assertRaises(ValidationError):
            review_ceo_tax_verification_candidate(
                self.ceo, altered
            )

    def test_06_missing_preparer_denied(self):
        altered = deepcopy(self.package)
        altered["payload"]["prepared_by"] = ""
        with self.assertRaises(ValidationError):
            review_ceo_tax_verification_candidate(
                self.ceo, altered
            )

    def test_07_no_audit_or_verification_write(self):
        before = AuditEvent.objects.count()
        result = review_ceo_tax_verification_candidate(
            self.ceo, self.package
        )
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertFalse(result["persisted_entry_authenticated"])

    def test_08_all_operational_actions_remain_denied(self):
        result = review_ceo_tax_verification_candidate(
            self.ceo, self.package
        )
        for field in (
            "verification_authorized",
            "independent_tax_entry_verified",
            "financial_report_eligible",
            "tax_posting_authorized",
            "tax_filing_authorized",
            "tax_payment_authorized",
        ):
            with self.subTest(field=field):
                self.assertFalse(result[field])

    def test_09_unregistered_ceo_actor_denied(self):
        other = User(
            username="unpersisted_ceo_4438l",
            role=Role.CEO,
        )
        with self.assertRaises(PermissionDenied):
            review_ceo_tax_verification_candidate(
                other, self.package
            )

    def test_10_original_package_not_modified(self):
        original = deepcopy(self.package)
        review_ceo_tax_verification_candidate(
            self.ceo, self.package
        )
        self.assertEqual(self.package, original)
