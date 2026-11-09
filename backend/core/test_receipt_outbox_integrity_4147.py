"""Characterize direct database bypass risks on disposable SQLite only.

These tests document weaknesses; they do not grant sending authority.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import ReceiptDispatchOutbox
from . import test_receipt_dispatch_outbox_4145 as fixture_module


class ReceiptOutboxIntegrityTests(TestCase):
    def setUp(self):
        fixture = fixture_module.ReceiptDispatchOutboxTests()
        fixture.setUp()
        self.entry = ReceiptDispatchOutbox.objects.create(**fixture.values)

    def test_database_rejects_sent_status_update(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReceiptDispatchOutbox.objects.filter(
                    pk=self.entry.pk
                ).update(status="SENT")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, "PENDING")

    def test_database_rejects_pending_recipient_update(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReceiptDispatchOutbox.objects.filter(
                    pk=self.entry.pk
                ).update(recipient_email="different@example.com")
        self.entry.refresh_from_db()
        self.assertEqual(
            self.entry.recipient_email, "customer@example.com"
        )

    def test_database_rejects_delete(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReceiptDispatchOutbox.objects.filter(
                    pk=self.entry.pk
                ).delete()
        self.assertTrue(
            ReceiptDispatchOutbox.objects.filter(
                pk=self.entry.pk
            ).exists()
        )
    def test_unique_key_remains_database_enforced(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReceiptDispatchOutbox.objects.bulk_create([
                    ReceiptDispatchOutbox(
                        project=self.entry.project,
                        msr=self.entry.msr,
                        document=self.entry.document,
                        requested_by=self.entry.requested_by,
                        idempotency_key=self.entry.idempotency_key,
                        recipient_email=self.entry.recipient_email,
                        pdf_sha256=self.entry.pdf_sha256,
                    ),
                ])
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)