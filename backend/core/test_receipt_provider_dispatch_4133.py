"""No-network provider dispatch authorization tests."""
import hashlib

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.test import SimpleTestCase

from .receipt_provider_dispatch import dispatch_receipt


class ReceiptProviderDispatchTests(SimpleTestCase):
    def setUp(self):
        pdf = b"%PDF-1.4\nProtected Receipt\n%%EOF"
        self.values = dict(
            pdf_bytes=pdf,
            expected_sha256=hashlib.sha256(pdf).hexdigest(),
            recipient="customer@example.com",
            approved_email="customer@example.com",
            connection=get_connection(
                backend="django.core.mail.backends.locmem.EmailBackend"
            ),
            mode="TEST_MEMORY",
        )

    def call(self, **changes):
        values = dict(self.values)
        values.update(changes)
        return dispatch_receipt(**values)

    def test_explicit_test_send_remains_untrusted(self):
        result = self.call()
        self.assertTrue(result.test_submission)
        self.assertFalse(result.provider_authenticated)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertEqual(len(mail.outbox), 1)

    def test_default_dispatch_denied(self):
        with self.assertRaises(ValidationError):
            self.call(mode="DISABLED")
        self.assertEqual(len(mail.outbox), 0)

    def test_production_mode_denied(self):
        with self.assertRaises(ValidationError):
            self.call(mode="PRODUCTION")
        self.assertEqual(len(mail.outbox), 0)

    def test_unconfigured_connection_denied(self):
        with self.assertRaises(ValidationError):
            self.call(connection=None)
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_customer_denied(self):
        with self.assertRaises(ValidationError):
            self.call(recipient="other@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_malformed_email_denied(self):
        with self.assertRaises(ValidationError):
            self.call(recipient="bad address")
        self.assertEqual(len(mail.outbox), 0)

    def test_wrong_pdf_fingerprint_denied(self):
        with self.assertRaises(ValidationError):
            self.call(expected_sha256="f" * 64)
        self.assertEqual(len(mail.outbox), 0)

    def test_non_pdf_denied(self):
        with self.assertRaises(ValidationError):
            self.call(pdf_bytes=b"not a PDF")
        self.assertEqual(len(mail.outbox), 0)