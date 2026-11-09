"""Isolated SQLite regression of outbox database immutability."""
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from .models import ReceiptDispatchOutbox
from . import test_receipt_dispatch_outbox_4145 as fixture_module


class OutboxDatabaseImmutabilityTests(TestCase):
    def setUp(self):
        fixture = fixture_module.ReceiptDispatchOutboxTests()
        fixture.setUp()
        self.entry = ReceiptDispatchOutbox.objects.create(**fixture.values)

    def test_database_update_of_recipient_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReceiptDispatchOutbox.objects.filter(
                    pk=self.entry.pk
                ).update(recipient_email="different@example.com")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.recipient_email, "customer@example.com")

    def test_database_update_of_digest_rejected(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReceiptDispatchOutbox.objects.filter(
                    pk=self.entry.pk
                ).update(pdf_sha256="0" * 64)
        self.entry.refresh_from_db()
        self.assertNotEqual(self.entry.pdf_sha256, "0" * 64)

    def test_database_delete_rejected(self):
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

    def test_both_sqlite_triggers_present(self):
        self.assertEqual(connection.vendor, "sqlite")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'trigger'
                AND tbl_name = 'core_receiptdispatchoutbox'
            """)
            names = {row[0] for row in cursor.fetchall()}
        self.assertIn("receipt_outbox_immutable_update", names)
        self.assertIn("receipt_outbox_immutable_delete", names)