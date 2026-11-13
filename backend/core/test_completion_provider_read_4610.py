"""Isolated provider-response validation; no network or database."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.exceptions import ValidationError

from .completion_provider_read_4610 import read_completed_certificate


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionProviderReadTests(SimpleTestCase):
    def setUp(self):
        self.account = str(uuid4())
        self.envelope = str(uuid4())
        now = timezone.now()
        self.completed = now.isoformat()
        self.gecc_signed = (
            now - timedelta(minutes=4)
        ).isoformat()
        self.customer_signed = (
            now - timedelta(minutes=2)
        ).isoformat()

        self.expected = {
            "documents": [
                {"documentId": "1", "name": "Completion.pdf"}
            ],
            "recipients": {
                "signers": [
                    {
                        "recipientId": "1",
                        "name": "Customer",
                        "email": "customer@example.test",
                        "routingOrder": "2",
                        "tabs": {},
                    },
                    {
                        "recipientId": "2",
                        "name": "GECC",
                        "email": "gecc@example.test",
                        "routingOrder": "1",
                        "tabs": {},
                    },
                ]
            },
        }

        self.summary = {
            "envelopeId": self.envelope,
            "status": "completed",
            "completedDateTime": self.completed,
        }
        self.recipients = {
            "signers": [
                {
                    **self.expected["recipients"]["signers"][0],
                    "status": "completed",
                    "signedDateTime": self.customer_signed,
                },
                {
                    **self.expected["recipients"]["signers"][1],
                    "status": "completed",
                    "signedDateTime": self.gecc_signed,
                },
            ]
        }
        self.documents = {
            "envelopeDocuments": [
                {"documentId": "1", "name": "Completion.pdf"},
                {"documentId": "certificate", "name": "Summary"},
            ]
        }

        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        stream = BytesIO()
        writer.write(stream)
        self.pdf = stream.getvalue()

    def run_read(self, *, summary=None, recipients=None,
                 documents=None, pdf=None, account=None,
                 expected=None):
        responses = [
            self.summary if summary is None else summary,
            self.recipients if recipients is None else recipients,
            self.documents if documents is None else documents,
            self.pdf if pdf is None else pdf,
            self.pdf if pdf is None else pdf,
        ]
        configuration = {
            "account_id": self.account,
            "blockers": [],
        }
        with patch(
            "core.completion_provider_read_4610.docusign.configuration",
            return_value=configuration,
        ), patch(
            "core.completion_provider_read_4610._read",
            side_effect=responses,
        ) as mocked:
            result = read_completed_certificate(
                account_id=self.account if account is None else account,
                envelope_id=self.envelope,
                token="test-access-token",
                expected=self.expected if expected is None else expected,
            )
        return result, mocked

    def test_valid_provider_bundle_has_no_completion_authority(self):
        result, mocked = self.run_read()
        self.assertEqual(mocked.call_count, 5)
        self.assertTrue(result["provider_response_validated"])
        self.assertEqual(len(result["pdf_manifest"]), 2)
        self.assertFalse(result["completion_authorized"])
        self.assertFalse(result["project_completed"])
        self.assertFalse(result["oauth_callback_binding_verified"])
        self.assertFalse(result["persisted_evidence_verified"])

    def test_wrong_envelope_denied(self):
        changed = {**self.summary, "envelopeId": str(uuid4())}
        with self.assertRaises(ValidationError):
            self.run_read(summary=changed)

    def test_incomplete_signer_denied(self):
        changed = {
            "signers": [
                {**item, "status": "sent"}
                for item in self.recipients["signers"]
            ]
        }
        with self.assertRaises(ValidationError):
            self.run_read(recipients=changed)

    def test_missing_certificate_document_denied(self):
        changed = {
            "envelopeDocuments": [
                {"documentId": "1", "name": "Completion.pdf"},
                {"documentId": "2", "name": "Unexpected.pdf"},
            ]
        }
        with self.assertRaises(ValidationError):
            self.run_read(documents=changed)

    def test_corrupt_pdf_denied(self):
        with self.assertRaises(ValidationError):
            self.run_read(pdf=b"%PDF-invalid")

    def test_wrong_account_denied(self):
        with self.assertRaises(ValidationError):
            self.run_read(account=str(uuid4()))

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_boundary_denied(self):
        with self.assertRaises(ValidationError):
            self.run_read()

    def test_unapproved_document_id_denied(self):
        changed = {
            **self.expected,
            "documents": [
                {"documentId": "../1", "name": "Completion.pdf"}
            ],
        }
        with self.assertRaises(ValidationError):
            self.run_read(expected=changed)
