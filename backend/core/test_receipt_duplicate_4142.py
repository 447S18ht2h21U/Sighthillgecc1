"""Database-backed sequential duplicate and failure tests."""
from datetime import timedelta
import hashlib
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.test import TestCase
from django.utils import timezone

from .models import Document, ReceiptSendingObservation, Role, User
from .receipt_secure_test_workflow import secure_test_receipt_dispatch
from . import test_installation_combined_real_evidence as fixture_module


class ReceiptDuplicateTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        fixture.snapshot["customer_email"] = "customer@example.com"
        self.msr = fixture.prepare()
        self.actor = User.objects.get(pk=self.msr.created_by_id)
        self.actor.role = Role.COMPTROLLER
        self.actor.is_active = True
        self.actor.save(update_fields=["role", "is_active"])

        self.pdf = b"%PDF-1.4\nTest Receipt 4142\n%%EOF"
        self.document = Document.objects.create(
            msr=self.msr,
            kind=Document.Kind.INVOICE,
            status="PREPARATION",
            created_by=self.actor,
            filename="test-receipt-4142.pdf",
            template_sha256="a" * 64,
            snapshot_sha256="b" * 64,
            pdf_sha256=hashlib.sha256(self.pdf).hexdigest(),
            renderer_version="1",
            values={},
            content=self.pdf,
        )
        self.values = dict(
            actor=self.actor,
            project_id=self.msr.project_id,
            document_id=self.document.pk,
            recipient="customer@example.com",
            pdf_bytes=self.pdf,
            observed_sent_at=timezone.now() - timedelta(minutes=1),
            connection=get_connection(
                backend="django.core.mail.backends.locmem.EmailBackend"
            ),
            provider_reference="TEST-4142-ONE",
        )

    def send(self, **overrides):
        values = dict(self.values)
        values.update(overrides)
        return secure_test_receipt_dispatch(**values)

    def test_first_send_creates_one_unverified_record(self):
        observation = self.send()
        self.assertEqual(observation.status, "UNVERIFIED")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ReceiptSendingObservation.objects.count(), 1)

    def test_duplicate_reference_blocked_before_second_email(self):
        self.send()
        with self.assertRaises(ValidationError):
            self.send()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ReceiptSendingObservation.objects.count(), 1)

    def test_different_reference_still_unverified(self):
        first = self.send()
        second = self.send(provider_reference="TEST-4142-TWO")
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(second.status, "UNVERIFIED")
        self.assertEqual(ReceiptSendingObservation.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_audit_failure_does_not_create_evidence(self):
        with patch(
            "core.receipt_observation_recording.audit",
            side_effect=RuntimeError("Test audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.send()
        self.assertFalse(ReceiptSendingObservation.objects.exists())
        # In-memory mail was submitted before the audit error.
        # This explicitly demonstrates why production needs an outbox
        # and reconciliation, not a claim of atomic email rollback.
        self.assertEqual(len(mail.outbox), 1)

    def test_wrong_recipient_sends_nothing(self):
        with self.assertRaises(ValidationError):
            self.send(recipient="wrong@example.com")
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReceiptSendingObservation.objects.exists())