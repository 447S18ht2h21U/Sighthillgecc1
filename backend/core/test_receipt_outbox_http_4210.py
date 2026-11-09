"""End-to-end HTTP tests; no operational URL registration."""
import time
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve

from .models import ReceiptDispatchOutbox, Role
from .test_receipt_dispatch_outbox_4145 import ReceiptDispatchOutboxTests


@override_settings(
    ROOT_URLCONF="core.receipt_outbox_test_urls_4210"
)
class ReceiptOutboxHTTPTests(TestCase):
    def setUp(self):
        fixture = ReceiptDispatchOutboxTests()
        fixture.setUp()
        self.project = fixture.project
        self.document = fixture.document
        self.actor = fixture.actor
        self.url = "/test-only/receipt-outbox/"
        self.payload = {
            "project_id": str(self.project.pk),
            "document_id": str(self.document.pk),
            "idempotency_key": "OUTBOX_HTTP_4210",
        }
        self.client.force_login(self.actor)

        # Initialize the genuine session activity timestamp.
        # Preserve the application's 30-minute idle timeout.
        session = self.client.session
        session["last_activity"] = time.time()
        session.save()

    def create(self, data=None):
        return self.client.post(
            self.url,
            data=self.payload if data is None else data,
            content_type="application/json",
        )

    def test_complete_http_request_and_status_flow(self):
        with patch(
            "core.receipt_outbox_request_service.audit"
        ) as audit:
            response = self.create()

        self.assertEqual(response.status_code, 202)
        created = response.json()
        self.assertEqual(created["status"], "PENDING")
        self.assertFalse(created["email_sent"])
        audit.assert_called_once()

        status_url = self.url + created["outbox_id"] + "/"
        status_response = self.client.get(status_url)

        self.assertEqual(status_response.status_code, 200)
        observed = status_response.json()
        self.assertEqual(observed["status"], "PENDING")
        self.assertFalse(observed["delivery_verified"])
        self.assertFalse(observed["completion_authorized"])
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_http_duplicate_is_rejected(self):
        with patch("core.receipt_outbox_request_service.audit"):
            self.assertEqual(self.create().status_code, 202)
            self.assertEqual(self.create().status_code, 400)

        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_http_anonymous_access_denied(self):
        self.client.logout()
        self.assertIn(self.create().status_code, (401, 403))
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_http_wrong_role_denied(self):
        self.actor.role = Role.SALES_ASSOCIATE
        self.actor.save(update_fields=["role"])
        self.assertEqual(self.create().status_code, 403)
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_http_payload_override_denied(self):
        data = {
            **self.payload,
            "recipient": "attacker@example.com",
        }
        self.assertEqual(self.create(data).status_code, 400)
        self.assertFalse(ReceiptDispatchOutbox.objects.exists())

    def test_http_unknown_status_is_not_found(self):
        response = self.client.get(
            self.url + "00000000-0000-4000-8000-000000000001/"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)

    def test_status_never_exposes_customer_email_or_pdf(self):
        with patch("core.receipt_outbox_request_service.audit"):
            response = self.create()

        self.assertEqual(response.status_code, 202)
        observed = self.client.get(
            self.url + response.json()["outbox_id"] + "/"
        )
        self.assertEqual(observed.status_code, 200)
        self.assertNotIn("recipient_email", observed.json())
        self.assertNotIn("pdf_sha256", observed.json())
        self.assertEqual(len(mail.outbox), 0)