"""Disposable database-backed tax evidence audit tests."""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, AuditHead, Customer, MSR, Project, Role, User
from .tax_evidence_audit_4437V import test_only_record_tax_evidence


class TaxEvidenceAudit4437VTests(TestCase):
    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        self.comp = User.objects.create_user(
            username="tax_audit_comp_4437v",
            password="fixture-only",
            role=Role.COMPTROLLER,
        )
        self.ceo = User.objects.create_user(
            username="tax_audit_ceo_4437v",
            password="fixture-only",
            role=Role.CEO,
        )
        customer = Customer.objects.create(
            legal_name="Synthetic Tax Customer",
            billing_address="Current billing",
            created_by=self.comp,
        )
        project = Project.objects.create(
            code="SYNTHETIC-TAX-4437V",
            customer=customer,
            location="Current installation",
            sales_associate=self.comp,
            reviewer=self.comp,
        )
        msr = MSR.objects.create(
            project=project,
            number=2,
            status="APPROVED",
            snapshot={
                "billing_address": "Historical billing DE",
                "project_location": "Historical installation MD",
                "customer": "Synthetic Tax Customer",
                "financing_type": "NON_FINANCED",
            },
            created_by=self.comp,
            prepared_by=self.comp,
            approved_by=self.comp,
        )
        Project.objects.filter(pk=project.pk).update(
            current_approved=msr
        )
        self.draft = {
            "tax_year": "2025",
            "accounting_period": "2026-10",
            "jurisdiction": "MARYLAND",
            "tax_category": "PROJECT_TAX_REVIEW",
            "accounting_classification": "OTHER_BUSINESS_TAX_EXPENSE",
            "amount": "125.00",
            "source_reference": "SYNTHETIC-SOURCE",
            "evidence_reference": "SYNTHETIC-DOCUMENT",
            "explanation": "Synthetic evidence only",
            "filing_status": "NOT_ESTABLISHED",
            "project_related": True,
            "project_id": str(project.pk),
            "approved_msr_id": str(msr.pk),
            "approved_msr_version": 2,
        }

    def test_01_comptroller_writes_test_audit(self):
        result = test_only_record_tax_evidence(self.comp, self.draft)
        self.assertEqual(result["status"], "ISOLATED_TEST_AUDIT_ONLY")
        event = AuditEvent.objects.get(pk=result["audit_event_id"])
        self.assertEqual(
            event.action, "tax_draft.test_evidence_prepared"
        )
        self.assertEqual(
            event.payload["evidence_sha256"],
            result["evidence_sha256"],
        )

    def test_02_audit_does_not_claim_verification(self):
        result = test_only_record_tax_evidence(self.comp, self.draft)
        self.assertFalse(result["tax_entry_verified"])
        self.assertFalse(result["financial_report_eligible"])
        event = AuditEvent.objects.get(pk=result["audit_event_id"])
        self.assertFalse(event.payload["tax_entry_verified"])

    def test_03_ceo_cannot_prepare_test_audit(self):
        before = AuditEvent.objects.count()
        with self.assertRaises(PermissionDenied):
            test_only_record_tax_evidence(self.ceo, self.draft)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_04_missing_document_evidence_denied(self):
        before = AuditEvent.objects.count()
        bad = dict(self.draft, evidence_reference="")
        with self.assertRaises(ValidationError):
            test_only_record_tax_evidence(self.comp, bad)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_05_invalid_msr_version_denied(self):
        before = AuditEvent.objects.count()
        bad = dict(self.draft, approved_msr_version=99)
        with self.assertRaises(ValidationError):
            test_only_record_tax_evidence(self.comp, bad)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_06_inactive_preparer_denied(self):
        self.comp.is_active = False
        self.comp.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            test_only_record_tax_evidence(self.comp, self.draft)

    def test_07_test_authorization_flag_required(self):
        with patch.dict(
            "os.environ",
            {"VERIDIAN_TAX_AUDIT_TEST_ONLY": ""},
        ):
            with self.assertRaises(PermissionDenied):
                test_only_record_tax_evidence(self.comp, self.draft)

    def test_08_reject_tampered_role_in_database(self):
        User.objects.filter(pk=self.comp.pk).update(role=Role.CEO)
        with self.assertRaises(PermissionDenied):
            test_only_record_tax_evidence(self.comp, self.draft)
    def test_09_production_environment_denied(self):
        from django.test import override_settings
        before = AuditEvent.objects.count()
        with override_settings(ENVIRONMENT="production"):
            with self.assertRaises(PermissionDenied):
                test_only_record_tax_evidence(self.comp, self.draft)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_10_file_based_sqlite_identity_denied(self):
        from django.db import connection
        from unittest.mock import patch
        before = AuditEvent.objects.count()
        with patch.dict(connection.settings_dict, {"NAME": "dev.sqlite3"}):
            with self.assertRaises(PermissionDenied):
                test_only_record_tax_evidence(self.comp, self.draft)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_11_unauthorized_sqlite_path_denied(self):
        from unittest.mock import patch
        before = AuditEvent.objects.count()
        with patch.dict(
            "os.environ", {"GECC_SQLITE_PATH": "dev.sqlite3"}
        ):
            with self.assertRaises(PermissionDenied):
                test_only_record_tax_evidence(self.comp, self.draft)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_12_missing_test_authorization_denied(self):
        from unittest.mock import patch
        before = AuditEvent.objects.count()
        with patch.dict(
            "os.environ",
            {"VERIDIAN_TAX_AUDIT_TEST_ONLY": ""},
        ):
            with self.assertRaises(PermissionDenied):
                test_only_record_tax_evidence(self.comp, self.draft)
        self.assertEqual(AuditEvent.objects.count(), before)
