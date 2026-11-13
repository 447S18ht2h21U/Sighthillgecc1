"""Disposable-SQLite acceptance for real draft retention and audit."""

import os
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from . import test_final_receipt_package_4797 as fixture
from .final_receipt_package_4797 import build_receipt_package_draft
from .models import AuditEvent, ReceiptDraftPackage
from .receipt_draft_retention_4803 import (
    retain_receipt_draft_package,
    verify_retained_draft_package,
)


SERVICE = "core.receipt_draft_retention_4803"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class DraftRetentionAcceptance4803(TestCase):
    setUp = fixture.PairedDraftAcceptance4797.setUp
    prepare_real_evidence = (
        fixture.PairedDraftAcceptance4797.prepare_real_evidence
    )
    decide = fixture.PairedDraftAcceptance4797.decide
    prepare_pair = fixture.PairedDraftAcceptance4797.prepare_pair

    def prepare_package(self):
        receipt, addendum, _ = self.prepare_pair()
        return build_receipt_package_draft(
            project=self.project,
            receipt=receipt,
            addendum=addendum,
        )

    def retain(self, package, *, actor=None):
        with patch.dict(
            os.environ,
            {"GECC_RECEIPT_DRAFT_RETENTION_TEST_ENABLED": "1"},
        ):
            return retain_receipt_draft_package(
                actor=actor if actor is not None else self.comptroller,
                project_id=self.project.pk,
                package=package,
            )

    def test_verified_package_retained_with_audit(self):
        package = self.prepare_package()
        baseline = AuditEvent.objects.count()

        record, created = self.retain(package)

        self.assertTrue(created)
        self.assertEqual(ReceiptDraftPackage.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), baseline + 1)
        self.assertEqual(bytes(record.content), package.archive)

        verified = verify_retained_draft_package(
            project=self.project, record=record,
        )

        self.assertTrue(verified.integrity_verified)
        self.assertFalse(verified.issuance_authorized)
        self.assertFalse(verified.customer_delivery_verified)

        print("PASS: Exact draft ZIP retained and independently verified.")
        print("PASS: Chained audit event created in same transaction.")

    def test_idempotency_no_duplicate_or_second_audit(self):
        package = self.prepare_package()
        first, created = self.retain(package)
        self.assertTrue(created)
        audit_count = AuditEvent.objects.count()

        second, created = self.retain(package)

        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ReceiptDraftPackage.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), audit_count)

        print("PASS: Repeated identical request is idempotent.")

    def test_disabled_switch_and_wrong_role_rejected(self):
        package = self.prepare_package()

        with patch.dict(
            os.environ,
            {"GECC_RECEIPT_DRAFT_RETENTION_TEST_ENABLED": "0"},
        ):
            with self.assertRaises(PermissionDenied):
                retain_receipt_draft_package(
                    actor=self.comptroller,
                    project_id=self.project.pk,
                    package=package,
                )

        from .models import Role, User
        unauthorized = (
            User.objects.filter(is_active=True)
            .exclude(role=Role.COMPTROLLER)
            .first()
        )
        self.assertIsNotNone(unauthorized)

        with self.assertRaises(PermissionDenied):
            self.retain(package, actor=unauthorized)

        self.assertEqual(ReceiptDraftPackage.objects.count(), 0)

        print("PASS: Disabled switch and unauthorized actor rejected.")

    def test_audit_failure_rolls_back_package(self):
        package = self.prepare_package()

        with patch(
            SERVICE + ".audit",
            side_effect=RuntimeError("FICTIONAL AUDIT FAILURE"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "FICTIONAL AUDIT FAILURE"
            ):
                self.retain(package)

        self.assertEqual(ReceiptDraftPackage.objects.count(), 0)

        print("PASS: Audit failure atomically rolls back retention.")
