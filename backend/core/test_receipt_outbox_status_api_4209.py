"""Focused unregistered status API security tests."""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import Resolver404, resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import ReceiptDispatchOutbox, Role
from .receipt_outbox_request_service import request_receipt_outbox
from .receipt_outbox_status_api_prototype_4209 import (
    ReceiptOutboxStatusPrototype,
)
from .test_receipt_dispatch_outbox_4145 import (
    ReceiptDispatchOutboxTests,
)


class ReceiptOutboxStatusPrototypeTests(TestCase):
    def setUp(self):
        fixture = ReceiptDispatchOutboxTests()
        fixture.setUp()
        self.project = fixture.project
        self.document = fixture.document
        self.actor = fixture.actor
        self.factory = APIRequestFactory()

        with patch("core.receipt_outbox_request_service.audit"):
            self.entry = request_receipt_outbox(
                actor=self.actor,
                project_id=self.project.pk,
                document_id=self.document.pk,
                recipient="customer@example.com",
                pdf_bytes=fixture.pdf,
                idempotency_key="OUTBOX_STATUS_4209",
            )

    def inspect(self, identifier=None, authenticated=True):
        request = self.factory.get(
            "/unregistered-receipt-outbox-status/"
        )
        if authenticated:
            force_authenticate(request, user=self.actor)
        return ReceiptOutboxStatusPrototype.as_view()(
            request,
            outbox_id=str(self.entry.pk)
            if identifier is None else identifier,
        )

    def test_comptroller_can_read_pending_status(self):
        response = self.inspect()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(
            response.data["outbox_id"], str(self.entry.pk)
        )
        self.assertFalse(response.data["email_sent"])
        self.assertFalse(response.data["provider_authenticated"])
        self.assertFalse(response.data["delivery_verified"])
        self.assertFalse(response.data["completion_authorized"])

    def test_status_response_excludes_sensitive_content(self):
        response = self.inspect()
        self.assertEqual(
            set(response.data),
            {
                "outbox_id", "project_id", "document_id", "status",
                "email_sent", "provider_authenticated",
                "delivery_verified", "completion_authorized",
            },
        )
        self.assertNotIn("recipient_email", response.data)
        self.assertNotIn("pdf_sha256", response.data)

    def test_anonymous_user_denied(self):
        response = self.inspect(authenticated=False)
        self.assertIn(response.status_code, (401, 403))

    def test_wrong_role_denied(self):
        self.actor.role = Role.SALES_ASSOCIATE
        self.actor.save(update_fields=["role"])
        self.assertEqual(self.inspect().status_code, 403)

    def test_inactive_comptroller_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        self.assertIn(self.inspect().status_code, (401, 403))

    def test_invalid_identifier_denied(self):
        response = self.inspect("not-a-uuid")
        self.assertEqual(response.status_code, 404)

    def test_missing_identifier_denied(self):
        response = self.inspect(
            "00000000-0000-4000-8000-000000000001"
        )
        self.assertEqual(response.status_code, 404)

    def test_status_check_does_not_modify_record_or_send(self):
        original = {
            "status": self.entry.status,
            "key": self.entry.idempotency_key,
            "count": ReceiptDispatchOutbox.objects.count(),
        }
        response = self.inspect()
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, original["status"])
        self.assertEqual(
            self.entry.idempotency_key, original["key"]
        )
        self.assertEqual(
            ReceiptDispatchOutbox.objects.count(),
            original["count"],
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_no_operational_status_route_registered(self):
        for path in (
            "/api/receipt-outbox/status/",
            "/api/receipt-outbox/",
        ):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)