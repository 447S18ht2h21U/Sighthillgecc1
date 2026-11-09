"""Focused database-backed CEO decision and audit safety tests."""
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    AuditEvent, AuditHead, Customer, MSR, Outbox, Project, Role, User,
)
from .tax_draft_evidence_4437U import prepare_tax_evidence_package
from .tax_version_persistence_4438P import (
    install_disposable_tax_table, remove_disposable_tax_table,
    store_disposable_tax_version, read_disposable_tax_version,
)
from .tax_ceo_decision_4438R import (
    DECISION_TABLE, install_disposable_decision_table,
    remove_disposable_decision_table, record_disposable_ceo_decision,
)


class TaxCEODecision4438RTests(TestCase):
    def setUp(self):
        install_disposable_tax_table()
        install_disposable_decision_table()
        AuditHead.objects.get_or_create(pk=1)

        self.comp = User.objects.create_user(
            username="tax_decision_comp_4438r",
            password="test-only", role=Role.COMPTROLLER,
        )
        self.ceo = User.objects.create_user(
            username="tax_decision_ceo_4438r",
            password="test-only", role=Role.CEO,
        )
        customer = Customer.objects.create(
            legal_name="Synthetic Decision Customer",
            billing_address="Synthetic billing",
            created_by=self.comp,
        )
        project = Project.objects.create(
            code="SYNTHETIC-TAX-4438R", customer=customer,
            location="Synthetic installation",
            sales_associate=self.comp, reviewer=self.comp,
        )
        msr = MSR.objects.create(
            project=project, number=1, status="APPROVED",
            snapshot={
                "customer": "Synthetic Decision Customer",
                "financing_type": "NON_FINANCED",
                "billing_address": "Approved billing",
                "project_location": "Approved installation",
            },
            created_by=self.comp, prepared_by=self.comp,
            approved_by=self.comp,
        )
        Project.objects.filter(pk=project.pk).update(
            current_approved=msr
        )
        package = prepare_tax_evidence_package(
            self.comp,
            {
                "tax_year": "2025",
                "accounting_period": "2026-10",
                "jurisdiction": "MARYLAND",
                "tax_category": "PROJECT_TAX_REVIEW",
                "accounting_classification":
                    "OTHER_BUSINESS_TAX_EXPENSE",
                "amount": "125.00",
                "source_reference": "SYNTHETIC-SOURCE",
                "evidence_reference": "SYNTHETIC-DOCUMENT",
                "explanation": "Test only",
                "filing_status": "NOT_ESTABLISHED",
                "project_related": True,
                "project_id": str(project.pk),
                "approved_msr_id": str(msr.pk),
                "approved_msr_version": 1,
            },
        )
        self.entry = store_disposable_tax_version(
            self.comp, package, series_id=str(uuid4()), version=1,
        )

    def tearDown(self):
        remove_disposable_decision_table()
        remove_disposable_tax_table()

    def decide(self):
        return record_disposable_ceo_decision(
            self.ceo, self.entry["id"]
        )

    def decision_count(self):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {DECISION_TABLE}")
            return cursor.fetchone()[0]

    def test_01_ceo_decision_uses_stored_entry(self):
        result = self.decide()
        self.assertEqual(result["decision"], "TEST_CEO_VERIFIED_ONLY")
        self.assertFalse(result["operational_verification_authorized"])
        self.assertFalse(result["financial_report_eligible"])

    def test_02_ceo_decision_has_atomic_audit_and_outbox(self):
        result = self.decide()
        event = AuditEvent.objects.get(
            action="tax_test.ceo_decision"
        )
        self.assertEqual(str(event.entity_id), result["decision_id"])
        self.assertTrue(Outbox.objects.filter(event=event).exists())

    def test_03_second_decision_rejected(self):
        self.decide()
        with self.assertRaises(ValidationError):
            self.decide()
        self.assertEqual(self.decision_count(), 1)

    def test_04_comptroller_cannot_decide(self):
        with self.assertRaises(PermissionDenied):
            record_disposable_ceo_decision(
                self.comp, self.entry["id"]
            )
        self.assertEqual(self.decision_count(), 0)

    def test_05_inactive_ceo_denied(self):
        User.objects.filter(pk=self.ceo.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.decide()

    def test_06_missing_preparation_audit_denied(self):
        with patch(
            "core.tax_ceo_decision_4438R.AuditEvent.objects.filter"
        ) as audit_filter:
            audit_filter.return_value.first.return_value = None
            with self.assertRaises(ValidationError):
                self.decide()
        self.assertEqual(self.decision_count(), 0)

    def test_07_outbox_failure_rolls_back_decision(self):
        before = AuditEvent.objects.count()
        with patch.object(
            Outbox.objects, "create",
            side_effect=RuntimeError("Synthetic decision audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Synthetic decision audit failure"
            ):
                self.decide()
        self.assertEqual(self.decision_count(), 0)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_08_database_blocks_decision_mutation(self):
        result = self.decide()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {DECISION_TABLE} WHERE id = %s",
                        [result["decision_id"]],
                    )
        self.assertEqual(self.decision_count(), 1)

    def corrected_after_rejection(self):
        from .tax_rejection_correction_4438V import (
            correct_rejected_tax_version,
        )
        record_disposable_ceo_decision(
            self.ceo, self.entry["id"],
            decision="TEST_CEO_REJECTED_ONLY",
            reason="Original evidence must be corrected.",
        )
        project = Project.objects.get(code="SYNTHETIC-TAX-4438R")
        msr = project.current_approved
        draft = {
            "tax_year": "2025",
            "accounting_period": "2026-10",
            "jurisdiction": "MARYLAND",
            "tax_category": "PROJECT_TAX_REVIEW",
            "accounting_classification": "OTHER_BUSINESS_TAX_EXPENSE",
            "amount": "125.00",
            "source_reference": "SYNTHETIC-SOURCE",
            "evidence_reference": "SYNTHETIC-REVISED-EVIDENCE",
            "explanation": "Corrected test evidence",
            "filing_status": "NOT_ESTABLISHED",
            "project_related": True,
            "project_id": str(project.pk),
            "approved_msr_id": str(msr.pk),
            "approved_msr_version": 1,
        }
        corrected_package = prepare_tax_evidence_package(
            self.comp, draft
        )
        result = correct_rejected_tax_version(
            self.comp, self.entry["id"], corrected_package
        )
        return read_disposable_tax_version(
            result["corrected_entry_id"]
        )

    def test_09_outdated_version_cannot_be_decided(self):
        old_entry_id = self.entry["id"]
        newer = self.corrected_after_rejection()
        self.assertEqual(newer["version"], 2)

        before = AuditEvent.objects.filter(
            action="tax_test.ceo_decision"
        ).count()
        with self.assertRaisesRegex(
            ValidationError, "Outdated tax-entry version"
        ):
            record_disposable_ceo_decision(self.ceo, old_entry_id)

        self.assertEqual(self.decision_count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="tax_test.ceo_decision"
            ).count(),
            before,
        )
        self.assertEqual(
            read_disposable_tax_version(old_entry_id)["version"],
            1,
        )

    def test_10_latest_version_can_receive_test_decision(self):
        newer = self.corrected_after_rejection()
        result = record_disposable_ceo_decision(
            self.ceo, newer["id"]
        )
        self.assertEqual(result["entry_id"], newer["id"])
        self.assertEqual(result["decision"], "TEST_CEO_VERIFIED_ONLY")
        self.assertFalse(result["operational_verification_authorized"])
        self.assertFalse(result["financial_report_eligible"])
        self.assertEqual(self.decision_count(), 2)

    def test_11_rejection_requires_explanation(self):
        for value in (None, "", "   ", "X" * 2001, ["not text"]):
            with self.subTest(reason=str(value)[:30]):
                with self.assertRaises(ValidationError):
                    record_disposable_ceo_decision(
                        self.ceo, self.entry["id"],
                        decision="TEST_CEO_REJECTED_ONLY",
                        reason=value,
                    )
        self.assertEqual(self.decision_count(), 0)

    def test_12_rejection_is_immutable_and_audited(self):
        result = record_disposable_ceo_decision(
            self.ceo, self.entry["id"],
            decision="TEST_CEO_REJECTED_ONLY",
            reason="  Missing supporting tax document.  ",
        )
        self.assertEqual(
            result["decision"], "TEST_CEO_REJECTED_ONLY"
        )
        self.assertEqual(
            result["reason"], "Missing supporting tax document."
        )
        event = AuditEvent.objects.get(
            action="tax_test.ceo_decision"
        )
        self.assertEqual(
            event.payload["decision"], "TEST_CEO_REJECTED_ONLY"
        )
        self.assertEqual(
            event.payload["reason"],
            "Missing supporting tax document."
        )
        self.assertTrue(Outbox.objects.filter(event=event).exists())
        self.assertFalse(result["operational_verification_authorized"])
        self.assertFalse(result["financial_report_eligible"])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {DECISION_TABLE} SET reason = %s "
                        "WHERE id = %s",
                        ["Changed reason", result["decision_id"]],
                    )
        self.assertEqual(self.decision_count(), 1)

    def test_13_unsupported_decision_rejected(self):
        for value in (
            "APPROVED",
            "TAX_PAYMENT_AUTHORIZED",
            "",
            None,
        ):
            with self.subTest(decision=value):
                with self.assertRaises(ValidationError):
                    record_disposable_ceo_decision(
                        self.ceo, self.entry["id"],
                        decision=value,
                    )
        self.assertEqual(self.decision_count(), 0)

    def test_14_rejected_version_cannot_be_verified_again(self):
        record_disposable_ceo_decision(
            self.ceo, self.entry["id"],
            decision="TEST_CEO_REJECTED_ONLY",
            reason="Incorrect evidence.",
        )
        before = AuditEvent.objects.filter(
            action="tax_test.ceo_decision"
        ).count()
        with self.assertRaises(ValidationError):
            self.decide()
        self.assertEqual(self.decision_count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="tax_test.ceo_decision"
            ).count(),
            before,
        )

    def test_11_direct_unaudited_version_insert_blocked(self):
        original_decisions = self.decision_count()

        with self.assertRaisesRegex(
            DatabaseError,
            "Tax revision requires preceding CEO rejection",
        ):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO tax_test_entry_4438p
                           (id, series_id, version, prepared_by,
                            evidence_sha256, evidence_json, status)
                           SELECT %s, series_id, 2, prepared_by,
                                  evidence_sha256, evidence_json, status
                           FROM tax_test_entry_4438p
                           WHERE id = %s""",
                        [str(uuid4()), self.entry["id"]],
                    )

        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COUNT(*) FROM tax_test_entry_4438p
                   WHERE series_id = %s""",
                [self.entry["series_id"]],
            )
            self.assertEqual(cursor.fetchone()[0], 1)

        self.assertEqual(self.decision_count(), original_decisions)

    def test_12_direct_outdated_ceo_insert_blocked(self):
        newer = self.corrected_after_rejection()
        self.assertEqual(newer["version"], 2)
        before = self.decision_count()

        with self.assertRaisesRegex(
            DatabaseError,
            "Outdated tax entry cannot receive CEO decision",
        ):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO tax_test_ceo_decision_4438r
                           (id, entry_id, verifier_id, preparer_id,
                            evidence_sha256, decision, reason)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        [
                            str(uuid4()),
                            self.entry["id"],
                            str(self.ceo.pk),
                            str(self.comp.pk),
                            self.entry["evidence_sha256"],
                            "TEST_CEO_VERIFIED_ONLY",
                            "",
                        ],
                    )

        self.assertEqual(self.decision_count(), before)
        self.assertEqual(
            read_disposable_tax_version(self.entry["id"])["version"],
            1,
        )
