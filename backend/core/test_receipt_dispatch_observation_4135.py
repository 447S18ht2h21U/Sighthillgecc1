"""Database-enabled test-only dispatch and observation checks."""
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .receipt_dispatch_observation import (
    dispatch_and_observe_test_receipt,
)


class ReceiptDispatchObservationTests(TestCase):
    def setUp(self):
        pdf = b"%PDF-1.4\nTest Receipt\n%%EOF"
        self.values = dict(
            actor=SimpleNamespace(pk=uuid4()),
            project_id=uuid4(),
            document_id=uuid4(),
            pdf_bytes=pdf,
            expected_sha256=hashlib.sha256(pdf).hexdigest(),
            recipient="customer@example.com",
            approved_email="customer@example.com",
            observed_sent_at=timezone.now() - timedelta(minutes=1),
            connection=get_connection(
                backend="django.core.mail.backends.locmem.EmailBackend"
            ),
            provider_reference="TEST-4135",
        )

    def call(self, **changes):
        values = dict(self.values)
        values.update(changes)
        return dispatch_and_observe_test_receipt(**values)

    def test_send_records_only_unverified_observation(self):
        record = SimpleNamespace(status="UNVERIFIED")
        with patch(
            "core.receipt_dispatch_observation."
            "record_unverified_receipt_observation",
            return_value=record,
        ) as written:
            result = self.call()
        self.assertIs(result, record)
        self.assertEqual(len(mail.outbox), 1)
        written.assert_called_once()
        self.assertEqual(
            written.call_args.kwargs["observation_source"],
            "MANUAL_OBSERVATION",
        )

    def test_invalid_pdf_prevents_recording(self):
        with patch(
            "core.receipt_dispatch_observation."
            "record_unverified_receipt_observation"
        ) as written:
            with self.assertRaises(ValidationError):
                self.call(expected_sha256="0" * 64)
        written.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_recipient_prevents_recording(self):
        with patch(
            "core.receipt_dispatch_observation."
            "record_unverified_receipt_observation"
        ) as written:
            with self.assertRaises(ValidationError):
                self.call(recipient="wrong@example.com")
        written.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_real_provider_reference_denied(self):
        with self.assertRaises(ValidationError):
            self.call(provider_reference="REAL-provider-id")
        self.assertEqual(len(mail.outbox), 0)

    def test_empty_reference_denied(self):
        with self.assertRaises(ValidationError):
            self.call(provider_reference="")
        self.assertEqual(len(mail.outbox), 0)

    def test_permission_failure_propagates(self):
        with patch(
            "core.receipt_dispatch_observation."
            "record_unverified_receipt_observation",
            side_effect=PermissionDenied("Not authorized"),
        ):
            with self.assertRaises(PermissionDenied):
                self.call()

    def test_audit_failure_propagates(self):
        with patch(
            "core.receipt_dispatch_observation."
            "record_unverified_receipt_observation",
            side_effect=RuntimeError("Audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.call()

    def test_trusted_status_claim_denied(self):
        with patch(
            "core.receipt_dispatch_observation."
            "record_unverified_receipt_observation",
            return_value=SimpleNamespace(status="VERIFIED"),
        ):
            with self.assertRaises(ValidationError):
                self.call()