"""Real SQLite outbox authorization and durable audit regressions."""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import ReceiptDispatchOutbox, Role
from .receipt_outbox_request_service import request_receipt_outbox
from . import test_receipt_dispatch_outbox_4145 as prior


class OutboxRequestTests(TestCase):
    def setUp(self):
        fixture = prior.ReceiptDispatchOutboxTests()
        fixture.setUp()
        self.project = fixture.project
        self.msr = fixture.msr
        self.document = fixture.document
        self.actor = fixture.actor
        self.pdf = fixture.pdf
        self.params = dict(
            actor=self.actor, project_id=self.project.pk,
            document_id=self.document.pk,
            recipient="customer@example.com",
            pdf_bytes=self.pdf,
            idempotency_key="OUTBOX_REQ_4146",
        )

    def request(self, **changes):
        data = dict(self.params)
        data.update(changes)
        return request_receipt_outbox(**data)

    def test_request_is_pending_not_delivery(self):
        with patch(
            "core.receipt_outbox_request_service.audit"
        ) as audited:
            entry = self.request()
        self.assertEqual(entry.status, "PENDING")
        self.assertEqual(entry.msr_id, self.msr.pk)
        self.assertEqual(entry.document_id, self.document.pk)
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        audited.assert_called_once()

    def test_same_key_rejected_without_new_entry(self):
        with patch("core.receipt_outbox_request_service.audit"):
            self.request()
            with self.assertRaises(ValidationError):
                self.request()
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_customer_rejected_before_creation(self):
        with self.assertRaises(ValidationError):
            self.request(recipient="other@example.com")
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_different_pdf_rejected(self):
        with self.assertRaises(ValidationError):
            self.request(pdf_bytes=b"%PDF-1.4\nnot retained\n%%EOF")
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_inactive_comptroller_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.request()
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_wrong_role_denied(self):
        self.actor.role = Role.SALES_ASSOCIATE
        self.actor.save(update_fields=["role"])
        with self.assertRaises(PermissionDenied):
            self.request()
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_audit_failure_rolls_back_outbox_intent(self):
        with patch(
            "core.receipt_outbox_request_service.audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.request()
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_idempotency_key_rejected(self):
        with self.assertRaises(ValidationError):
            self.request(idempotency_key="bad key")
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())