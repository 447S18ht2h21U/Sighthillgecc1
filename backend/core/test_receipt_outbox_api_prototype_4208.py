"""Unregistered receipt API security and non-delivery tests."""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import Resolver404, resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import ReceiptDispatchOutbox, Role
from .receipt_outbox_api_prototype_4208 import ReceiptOutboxRequestPrototype
from .test_receipt_dispatch_outbox_4145 import ReceiptDispatchOutboxTests


class ReceiptOutboxAPIPrototypeTests(TestCase):
    def setUp(self):
        fixture = ReceiptDispatchOutboxTests()
        fixture.setUp()
        self.project = fixture.project
        self.document = fixture.document
        self.actor = fixture.actor
        self.factory = APIRequestFactory()
        self.payload = {
            "project_id": str(self.project.pk),
            "document_id": str(self.document.pk),
            "idempotency_key": "OUTBOX_API_4208",
        }

    def submit(self, data=None, user=True):
        request = self.factory.post(
            "/unregistered-receipt-outbox-prototype/",
            self.payload if data is None else data,
            format="json",
        )
        if user:
            force_authenticate(request, user=self.actor)
        return ReceiptOutboxRequestPrototype.as_view()(request)

    def test_authorized_request_is_pending_and_never_sends(self):
        with patch(
            "core.receipt_outbox_request_service.audit"
        ) as audited:
            response = self.submit()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertFalse(response.data["email_sent"])
        self.assertFalse(response.data["delivery_verified"])
        self.assertFalse(response.data["completion_authorized"])
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        audited.assert_called_once()

    def test_duplicate_idempotency_key_rejected(self):
        with patch("core.receipt_outbox_request_service.audit"):
            self.assertEqual(self.submit().status_code, 202)
            self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_anonymous_request_denied(self):
        self.assertIn(self.submit(user=False).status_code, (401, 403))
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_wrong_role_denied(self):
        self.actor.role = Role.SALES_ASSOCIATE
        self.actor.save(update_fields=["role"])
        self.assertEqual(self.submit().status_code, 403)
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_inactive_comptroller_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        self.assertIn(self.submit().status_code, (401, 403))
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_payload_cannot_override_recipient_or_pdf(self):
        payload = {
            **self.payload,
            "recipient": "attacker@example.com",
        }
        self.assertEqual(self.submit(payload).status_code, 400)
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_or_malformed_fields_denied(self):
        for payload in (
            {"project_id": self.payload["project_id"]},
            {**self.payload, "idempotency_key": "bad key"},
            {**self.payload, "document_id": "not-a-valid-id"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.submit(payload).status_code, 400)
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_invalid_document_not_found(self):
        payload = {**self.payload, "document_id": "999999999"}
        response = self.submit(payload)
        self.assertIn(response.status_code, (400, 404))
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_prototype_has_no_operational_route(self):
        for path in (
            "/api/receipt-outbox/",
            "/api/receipt-dispatch/",
        ):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)