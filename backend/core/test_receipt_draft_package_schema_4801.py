"""Immutable draft package schema acceptance in isolated SQLite."""

from hashlib import sha256

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from . import test_final_receipt_package_4797 as fixture
from .final_receipt_package_4797 import build_receipt_package_draft
from .final_receipt_package_verifier_4798 import (
    verify_receipt_package_draft,
)
from .models import ReceiptDraftPackage


@override_settings(DEBUG=True, ENVIRONMENT="development")
class ImmutableDraftPackageSchema4801(TestCase):
    setUp = fixture.PairedDraftAcceptance4797.setUp
    prepare_real_evidence = (
        fixture.PairedDraftAcceptance4797.prepare_real_evidence
    )
    decide = fixture.PairedDraftAcceptance4797.decide
    prepare_pair = fixture.PairedDraftAcceptance4797.prepare_pair

    def create_package(self):
        receipt, addendum, _ = self.prepare_pair()
        package = build_receipt_package_draft(
            project=self.project,
            receipt=receipt,
            addendum=addendum,
        )
        verified = verify_receipt_package_draft(
            project=self.project, package=package,
        )
        self.assertTrue(verified.integrity_verified)

        record = ReceiptDraftPackage.objects.create(
            project=self.project,
            msr=self.msr,
            created_by=self.comptroller,
            snapshot_sha256=package.snapshot_sha256,
            approved_reference_sha256=(
                __import__(
                    "core.approved_final_receipt_reference_4756",
                    fromlist=["APPROVED_SHA256"],
                ).APPROVED_SHA256.lower()
            ),
            receipt_sha256=package.receipt_sha256,
            addendum_sha256=package.addendum_sha256,
            archive_sha256=package.archive_sha256,
            equipment_count=verified.equipment_count,
            content=package.archive,
            status="DRAFT_NOT_ISSUED",
        )
        return record, package

    def test_real_package_storage_and_exact_bytes(self):
        record, package = self.create_package()
        stored = ReceiptDraftPackage.objects.get(pk=record.pk)

        self.assertEqual(bytes(stored.content), package.archive)
        self.assertEqual(
            sha256(bytes(stored.content)).hexdigest(),
            stored.archive_sha256,
        )
        self.assertEqual(stored.status, "DRAFT_NOT_ISSUED")
        self.assertEqual(stored.msr_id, self.msr.pk)

        print("PASS: Real paired ZIP retained with exact hash.")
        print("PASS: Approved MSR and draft-only status bound.")

    def test_orm_and_database_immutability(self):
        record, _ = self.create_package()

        record.status = "FINAL"
        with self.assertRaises(ValidationError):
            record.save()

        with self.assertRaises(ValidationError):
            record.delete()

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ReceiptDraftPackage.objects.filter(
                    pk=record.pk
                ).update(status="FINAL")

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ReceiptDraftPackage.objects.filter(
                    pk=record.pk
                ).delete()

        self.assertEqual(
            ReceiptDraftPackage.objects.get(pk=record.pk).status,
            "DRAFT_NOT_ISSUED",
        )

        print("PASS: ORM and SQLite trigger reject edits/deletes.")

    def test_duplicate_and_false_status_rejected(self):
        record, package = self.create_package()

        record.status = "FINAL"
        with self.assertRaises(ValidationError):
            record.full_clean()

        self.assertEqual(ReceiptDraftPackage.objects.count(), 1)

        with self.assertRaises(ValidationError):
            ReceiptDraftPackage.objects.create(
                project=self.project,
                msr=self.msr,
                created_by=self.comptroller,
                snapshot_sha256=package.snapshot_sha256,
                approved_reference_sha256="a" * 64,
                receipt_sha256=package.receipt_sha256,
                addendum_sha256=package.addendum_sha256,
                archive_sha256=package.archive_sha256,
                equipment_count=1,
                content=package.archive,
                status="FINAL",
            )

        print("PASS: FALSE FINAL status rejected.")
