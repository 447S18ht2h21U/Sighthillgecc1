"""No-network Receipt transport security regression."""
import hashlib
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from django.core import mail
from django.core.mail import get_connection
from django.core.mail.backends.console import EmailBackend as ConsoleBackend
from .receipt_email_transport import send_receipt_to_test_backend


class ReceiptTransportTests(SimpleTestCase):
    def setUp(self):
        self.pdf = b"%PDF-1.4\nfixture receipt\n%%EOF"
        self.kw = dict(
            pdf_bytes=self.pdf,
            expected_sha256=hashlib.sha256(self.pdf).hexdigest(),
            recipient="customer@example.com",
            approved_email="customer@example.com",
            connection=get_connection(
                backend="django.core.mail.backends.locmem.EmailBackend"
            ),
        )

    def send(self, **overrides):
        values = dict(self.kw)
        values.update(overrides)
        return send_receipt_to_test_backend(**values)

    def test_test_backend_submission_is_not_delivery_proof(self):
        result = self.send()
        self.assertTrue(result.submitted_to_test_backend)
        self.assertFalse(result.provider_authenticated)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertEqual(len(mail.outbox), 1)

    def test_exact_pdf_attachment(self):
        self.send()
        attachment = mail.outbox[0].attachments[0]
        self.assertEqual(attachment[1], self.pdf)
        self.assertEqual(attachment[2], "application/pdf")

    def test_no_backend_denied(self):
        with self.assertRaises(ValidationError):
            self.send(connection=None)

    def test_non_test_backend_denied(self):
        with self.assertRaises(ValidationError):
            self.send(connection=ConsoleBackend())

    def test_wrong_fingerprint_denied(self):
        with self.assertRaises(ValidationError):
            self.send(expected_sha256="0" * 64)

    def test_wrong_recipient_denied(self):
        with self.assertRaises(ValidationError):
            self.send(recipient="wrong@example.com")

    def test_non_pdf_denied(self):
        with self.assertRaises(ValidationError):
            self.send(pdf_bytes=b"not a pdf")

    def test_sender_override_denied(self):
        with self.assertRaises(ValidationError):
            self.send(from_email="other@example.com")