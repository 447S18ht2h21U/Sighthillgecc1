"""Real isolated DB with a test-only approved-MSR email fixture."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ReceiptSendingObservation, Role, User
from .receipt_observation_recording import record_unverified_receipt_observation
from . import test_receipt_sending_observation_4121 as previous


class ReceiptObservationRecordingTests(TestCase):
    def setUp(self):
        fixture = previous.ReceiptSendingObservationTests()
        fixture.setUp()
        self.msr = fixture.msr
        self.document = fixture.document
        self.actor = User.objects.get(pk=fixture.actor.pk)
        self.actor.role = Role.COMPTROLLER
        self.actor.is_active = True
        self.actor.save(update_fields=["role", "is_active"])

        # The earlier installation fixture has no usable customer email.
        # Set an approved-MSR email in this test's in-memory object only.
        # Never modify the immutable approved MSR in the database.
        self.customer_email = "customer@example.com"
        self.msr.snapshot = {
            **self.msr.snapshot,
            "customer_email": self.customer_email,
        }
        self.project = self.msr.project
        self.project.current_approved = self.msr

        self.values = dict(
            actor=self.actor,
            project_id=self.project.pk,
            document_id=self.document.pk,
            recipient_email=self.customer_email,
            provider_reference="candidate-reference-4124",
            observed_sent_at=timezone.now() - timedelta(minutes=2),
        )

    def record(self, **changes):
        values = dict(self.values)
        values.update(changes)
        # Substitute only the test's project lookup. Document and
        # observation records, user roles and transactions remain real.
        with patch(
            "core.receipt_observation_recording.Project.objects.select_for_update"
        ) as locked:
            locked.return_value.get.return_value = self.project
            return record_unverified_receipt_observation(**values)

    def test_valid_observation_still_unverified_and_audited(self):
        with patch("core.receipt_observation_recording.audit") as audited:
            record = self.record()
        self.assertEqual(record.status, "UNVERIFIED")
        self.assertEqual(record.msr_id, self.msr.pk)
        self.assertEqual(record.document_id, self.document.pk)
        audited.assert_called_once()

    def test_inactive_actor_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.record()
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_non_comptroller_denied(self):
        self.actor.role = Role.SALES_ASSOCIATE
        self.actor.save(update_fields=["role"])
        with self.assertRaises(PermissionDenied):
            self.record()
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_wrong_customer_email_denied(self):
        with self.assertRaises(ValidationError):
            self.record(recipient_email="wrong@example.com")
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_missing_approved_customer_email_denied(self):
        self.msr.snapshot["customer_email"] = ""
        with self.assertRaises(ValidationError):
            self.record()
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_wrong_document_denied(self):
        from .models import Document
        with self.assertRaises(Document.DoesNotExist):
            self.record(document_id=uuid4())
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_audit_failure_rolls_back_record(self):
        with patch(
            "core.receipt_observation_recording.audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.record()
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_future_timestamp_denied(self):
        with self.assertRaises(ValidationError):
            self.record(
                observed_sent_at=timezone.now() + timedelta(days=1)
            )
        self.assertFalse(ReceiptSendingObservation.objects.exists())