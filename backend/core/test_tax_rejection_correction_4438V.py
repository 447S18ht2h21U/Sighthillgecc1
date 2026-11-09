"""Focused test-only rejected tax version correction tests."""
from uuid import UUID
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_tax_ceo_decision_4438R as fixture
from .models import AuditEvent, AuditHead, Outbox, Project
from .tax_ceo_decision_4438R import record_disposable_ceo_decision
from .tax_draft_evidence_4437U import prepare_tax_evidence_package
from .tax_rejection_correction_4438V import correct_rejected_tax_version
from .tax_version_persistence_4438P import read_disposable_tax_version


class TaxRejectionCorrection4438VTests(TestCase):
    def setUp(self):
        fixture.TaxCEODecision4438RTests.setUp(self)

    def tearDown(self):
        fixture.TaxCEODecision4438RTests.tearDown(self)

    def reject(self):
        return record_disposable_ceo_decision(
            self.ceo,
            self.entry["id"],
            decision="TEST_CEO_REJECTED_ONLY",
            reason="Incorrect tax evidence.",
        )

    def corrected_package(self):
        project = Project.objects.get(code="SYNTHETIC-TAX-4438R")
        msr = project.current_approved

        return prepare_tax_evidence_package(
            self.comp,
            {
                "tax_year": "2025",
                "accounting_period": "2026-10",
                "jurisdiction": "MARYLAND",
                "tax_category": "PROJECT_TAX_REVIEW",
                "accounting_classification":
                    "OTHER_BUSINESS_TAX_EXPENSE",
                "amount": "125.00",
                "source_reference": "SYNTHETIC-SOURCE-CORRECTED",
                "evidence_reference": "SYNTHETIC-DOCUMENT-CORRECTED",
                "explanation": "Corrected supporting evidence.",
                "filing_status": "NOT_ESTABLISHED",
                "project_related": True,
                "project_id": str(project.pk),
                "approved_msr_id": str(msr.pk),
                "approved_msr_version": 1,
            },
        )

    def test_01_rejection_creates_new_unverified_version(self):
        rejection = self.reject()
        result = correct_rejected_tax_version(
            self.comp, self.entry["id"], self.corrected_package()
        )
        corrected = read_disposable_tax_version(
            result["corrected_entry_id"]
        )
        self.assertEqual(corrected["version"], 2)
        self.assertEqual(corrected["status"], "UNVERIFIED_DRAFT_ONLY")
        self.assertEqual(
            result["rejection_decision_id"], rejection["decision_id"]
        )
        self.assertTrue(result["requires_new_ceo_decision"])
        self.assertFalse(result["operational_verification_authorized"])

    def test_02_original_rejection_and_correction_audited(self):
        rejection = self.reject()
        old = read_disposable_tax_version(self.entry["id"])
        result = correct_rejected_tax_version(
            self.comp, self.entry["id"], self.corrected_package()
        )
        self.assertEqual(
            read_disposable_tax_version(self.entry["id"]), old
        )
        correction_event = AuditEvent.objects.get(
            action="tax_test.rejection_corrected",
            entity_id=UUID(result["corrected_entry_id"]),
        )
        self.assertEqual(
            correction_event.payload["rejection_decision_id"],
            rejection["decision_id"],
        )
        self.assertTrue(
            Outbox.objects.filter(event=correction_event).exists()
        )

    def test_03_missing_rejection_denies_correction(self):
        with self.assertRaises(ValidationError):
            correct_rejected_tax_version(
                self.comp, self.entry["id"], self.corrected_package()
            )

    def test_04_unchanged_evidence_denies_correction(self):
        self.reject()
        with self.assertRaises(ValidationError):
            correct_rejected_tax_version(
                self.comp, self.entry["id"], self.entry["evidence"]
            )

    def test_05_verified_entry_or_ceo_cannot_correct(self):
        record_disposable_ceo_decision(
            self.ceo, self.entry["id"]
        )
        with self.assertRaises(ValidationError):
            correct_rejected_tax_version(
                self.comp, self.entry["id"], self.corrected_package()
            )
        with self.assertRaises(PermissionDenied):
            correct_rejected_tax_version(
                self.ceo, self.entry["id"], self.corrected_package()
            )

    def test_06_failed_correction_audit_rolls_back(self):
        self.reject()
        head = AuditHead.objects.get(pk=1)
        initial = (
            head.sequence,
            head.digest,
            AuditEvent.objects.count(),
            Outbox.objects.count(),
        )
        original_create = Outbox.objects.create

        def fail_correction_only(**kwargs):
            if kwargs.get("topic") == "tax_test.rejection_corrected":
                raise RuntimeError("Synthetic correction audit failure")
            return original_create(**kwargs)

        with patch.object(
            Outbox.objects,
            "create",
            side_effect=fail_correction_only,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Synthetic correction audit failure"
            ):
                correct_rejected_tax_version(
                    self.comp,
                    self.entry["id"],
                    self.corrected_package(),
                )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM tax_test_entry_4438p "
                "WHERE series_id = %s",
                [self.entry["series_id"]],
            )
            self.assertEqual(cursor.fetchone()[0], 1)

        head.refresh_from_db()
        self.assertEqual(
            (
                head.sequence,
                head.digest,
                AuditEvent.objects.count(),
                Outbox.objects.count(),
            ),
            initial,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action="tax_test.rejection_corrected"
            ).count(),
            0,
        )
        self.assertEqual(
            read_disposable_tax_version(self.entry["id"]),
            self.entry,
        )

    def test_07_corrected_version_requires_new_ceo_decision(self):
        original_rejection = self.reject()
        correction = correct_rejected_tax_version(
            self.comp,
            self.entry["id"],
            self.corrected_package(),
        )
        decision = record_disposable_ceo_decision(
            self.ceo,
            correction["corrected_entry_id"],
        )
        self.assertEqual(
            decision["entry_id"],
            correction["corrected_entry_id"],
        )
        self.assertNotEqual(
            decision["decision_id"],
            original_rejection["decision_id"],
        )
        self.assertEqual(
            decision["decision"],
            "TEST_CEO_VERIFIED_ONLY",
        )
        self.assertFalse(
            decision["operational_verification_authorized"]
        )
        self.assertFalse(decision["financial_report_eligible"])
