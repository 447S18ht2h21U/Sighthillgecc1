"""Isolated database verification of durable Receipt outbox intent."""
import hashlib

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Document, ReceiptDispatchOutbox, Role, User
from . import test_installation_combined_real_evidence as foundation


class ReceiptDispatchOutboxTests(TestCase):
    def setUp(self):
        fixture = foundation.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        fixture.snapshot["customer_email"] = "customer@example.com"
        self.msr = fixture.prepare()
        self.project = fixture.project
        self.actor = User.objects.get(pk=self.msr.created_by_id)
        self.actor.role = Role.COMPTROLLER
        self.actor.is_active = True
        self.actor.save(update_fields=["role", "is_active"])

        self.pdf = b"%PDF-1.4\nDurable test intent\n%%EOF"
        self.digest = hashlib.sha256(self.pdf).hexdigest()
        self.document = Document.objects.create(
            msr=self.msr,
            kind=Document.Kind.INVOICE,
            status="PREPARATION",
            created_by=self.actor,
            filename="outbox-test.pdf",
            template_sha256="a" * 64,
            snapshot_sha256="b" * 64,
            pdf_sha256=self.digest,
            renderer_version="1",
            values={},
            content=self.pdf,
        )
        self.values = dict(
            project=self.project,
            msr=self.msr,
            document=self.document,
            requested_by=self.actor,
            idempotency_key="RECEIPT_TEST_4145",
            recipient_email="customer@example.com",
            pdf_sha256=self.digest,
        )

    def create(self, **changes):
        data = dict(self.values)
        data.update(changes)
        return ReceiptDispatchOutbox.objects.create(**data)

    def test_pending_intent_has_no_delivery_authority(self):
        entry = self.create()
        self.assertEqual(entry.status, "PENDING")
        self.assertEqual(entry.document_id, self.document.pk)
        self.assertFalse(hasattr(entry, "delivery_verified"))

    def test_duplicate_key_blocked_at_database(self):
        self.create()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReceiptDispatchOutbox.objects.bulk_create([
                    ReceiptDispatchOutbox(**self.values),
                ])
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)

    def test_wrong_customer_email_denied(self):
        with self.assertRaises(ValidationError):
            self.create(recipient_email="wrong@example.com")
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_pdf_fingerprint_mismatch_denied(self):
        with self.assertRaises(ValidationError):
            self.create(pdf_sha256="0" * 64)

    def test_saved_outbox_entry_not_editable(self):
        entry = self.create()
        entry.recipient_email = "other@example.com"
        with self.assertRaises(ValidationError):
            entry.save()

    def test_saved_outbox_entry_not_deletable(self):
        entry = self.create()
        with self.assertRaises(ValidationError):
            entry.delete()

    def test_database_cannot_claim_sent_status(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReceiptDispatchOutbox.objects.bulk_create([
                    ReceiptDispatchOutbox(
                        **self.values, status="SENT",
                    ),
                ])
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())