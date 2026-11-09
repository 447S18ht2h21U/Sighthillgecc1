"""Database-backed isolated tax version, immutability and audit tests."""
from copy import deepcopy
from unittest.mock import patch
from uuid import UUID, uuid4

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, AuditHead, Customer, MSR, Outbox, Project, Role, User
from .tax_draft_evidence_4437U import prepare_tax_evidence_package
from .tax_version_persistence_4438P import (
    TABLE,
    install_disposable_tax_table,
    remove_disposable_tax_table,
    read_disposable_tax_version,
    require_isolated_tax_test,
    store_disposable_tax_version,
)


class TaxVersionPersistence4438PTests(TestCase):
    def setUp(self):
        install_disposable_tax_table()
        AuditHead.objects.get_or_create(pk=1)
        self.comp = User.objects.create_user(
            username="tax_store_comp_4438p",
            password="fixture-only",
            role=Role.COMPTROLLER,
        )
        self.ceo = User.objects.create_user(
            username="tax_store_ceo_4438p",
            password="fixture-only",
            role=Role.CEO,
        )
        customer = Customer.objects.create(
            legal_name="Synthetic Storage Customer",
            billing_address="Current billing",
            created_by=self.comp,
        )
        project = Project.objects.create(
            code="SYNTHETIC-TAX-4438P",
            customer=customer,
            location="Current site",
            sales_associate=self.comp,
            reviewer=self.comp,
        )
        msr = MSR.objects.create(
            project=project, number=2, status="APPROVED",
            snapshot={
                "customer": "Synthetic Storage Customer",
                "financing_type": "NON_FINANCED",
                "billing_address": "Approved billing",
                "project_location": "Approved site",
            },
            created_by=self.comp, prepared_by=self.comp,
            approved_by=self.comp,
        )
        Project.objects.filter(pk=project.pk).update(current_approved=msr)
        draft = {
            "tax_year": "2025",
            "accounting_period": "2026-10",
            "jurisdiction": "MARYLAND",
            "tax_category": "PROJECT_TAX_REVIEW",
            "accounting_classification": "OTHER_BUSINESS_TAX_EXPENSE",
            "amount": "125.00",
            "source_reference": "SYNTHETIC-SOURCE",
            "evidence_reference": "SYNTHETIC-DOCUMENT",
            "explanation": "Test-only evidence",
            "filing_status": "NOT_ESTABLISHED",
            "project_related": True,
            "project_id": str(project.pk),
            "approved_msr_id": str(msr.pk),
            "approved_msr_version": 2,
        }
        self.package = prepare_tax_evidence_package(self.comp, draft)
        self.series = str(uuid4())

    def tearDown(self):
        remove_disposable_tax_table()

    def store(self, **changes):
        args = {
            "series_id": self.series,
            "version": 1,
        }
        args.update(changes)
        return store_disposable_tax_version(
            self.comp, self.package, **args
        )

    def test_01_draft_is_independently_stored(self):
        record = self.store()
        self.assertEqual(record["status"], "UNVERIFIED_DRAFT_ONLY")
        self.assertEqual(record["prepared_by"], str(self.comp.pk))
        self.assertEqual(record["evidence"], self.package)
        self.assertFalse(record["independent_tax_entry_verified"])

    def test_02_preparation_has_audit_and_outbox(self):
        record = self.store()
        event = AuditEvent.objects.get(
            action="tax_test.version_prepared"
        )
        self.assertEqual(event.entity_id, __import__("uuid").UUID(record["id"]))
        self.assertTrue(Outbox.objects.filter(event=event).exists())
        self.assertEqual(
            event.payload["evidence_sha256"],
            record["evidence_sha256"],
        )

    def test_03_duplicate_series_version_rejected(self):
        self.store()
        with self.assertRaises(IntegrityError):
            self.store()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_04_database_blocks_direct_update(self):
        record = self.store()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {TABLE} SET status = %s WHERE id = %s",
                        ["UNVERIFIED_DRAFT_ONLY", record["id"]],
                    )
        self.assertEqual(
            read_disposable_tax_version(record["id"])["evidence"],
            self.package,
        )

    def test_05_database_blocks_direct_delete(self):
        record = self.store()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {TABLE} WHERE id = %s",
                        [record["id"]],
                    )
        self.assertEqual(
            read_disposable_tax_version(record["id"])["version"], 1
        )

    def test_06_ceo_cannot_prepare(self):
        with self.assertRaises(PermissionDenied):
            store_disposable_tax_version(
                self.ceo, self.package,
                series_id=self.series, version=1,
            )

    def test_07_tampered_evidence_rejected(self):
        altered = deepcopy(self.package)
        altered["payload"]["captured_draft"]["amount"] = "999.00"
        with self.assertRaises(ValidationError):
            store_disposable_tax_version(
                self.comp, altered,
                series_id=self.series, version=1,
            )

    def test_08_outbox_failure_rolls_back_record_and_audit(self):
        before = AuditEvent.objects.count()
        with patch.object(
            Outbox.objects, "create",
            side_effect=RuntimeError("Synthetic outbox failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Synthetic outbox failure"
            ):
                self.store()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
            self.assertEqual(cursor.fetchone()[0], 0)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_09_first_version_must_be_one(self):
        with self.assertRaises(ValidationError):
            self.store(version=2)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_10_skipped_version_rejected(self):
        self.store()
        with self.assertRaises(ValidationError):
            self.store(version=3)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
            self.assertEqual(cursor.fetchone()[0], 1)


    def test_11_direct_revision_without_rejection_denied(self):
        first = self.store()
        with self.assertRaises(ValidationError):
            self.store(version=2)
        self.assertEqual(
            read_disposable_tax_version(first["id"]), first
        )

    def test_12_original_evidence_unchanged_after_denial(self):
        first = self.store()
        with self.assertRaises(ValidationError):
            self.store(version=2)
        preserved = read_disposable_tax_version(first["id"])
        self.assertEqual(preserved["evidence"], self.package)
        self.assertEqual(preserved["version"], 1)

    def test_13_invented_rejection_reference_denied(self):
        self.store()
        with self.assertRaises(ValidationError):
            self.store(
                version=2,
                rejection_decision_id=str(uuid4()),
            )

    def test_14_invalid_rejection_identity_denied(self):
        self.store()
        with self.assertRaises(ValidationError):
            self.store(
                version=2,
                rejection_decision_id="not-a-uuid",
            )
