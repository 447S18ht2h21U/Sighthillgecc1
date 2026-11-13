"""Tests for bounded DocuSign sandbox request/response transport."""
import base64
import copy
import hashlib
import json
import os
from unittest.mock import patch
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from .completion_provider_transport_4630 import (
    prepare_sandbox_request, simulate_sandbox_draft_post,
)


class FakeResponse:
    def __init__(self, payload, status=201):
        self.status = status
        self.content = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.content[:limit]


@override_settings(DEBUG=True, ENVIRONMENT="development")
class CompletionProviderTransportTests(SimpleTestCase):
    def setUp(self):
        gate = patch.dict(
            os.environ,
            {"GECC_TEST_COMPLETION_TRANSPORT": "1"},
        )
        gate.start()
        self.addCleanup(gate.stop)
        self.account = str(uuid4())
        self.attempt = str(uuid4())
        self.envelope = str(uuid4())
        pdf = b"%PDF-1.4\nsynthetic test fixture\n%%EOF"
        self.digest = hashlib.sha256(pdf).hexdigest()

        self.prepared = SimpleNamespace(
            account_id=self.account,
            attempt_id=self.attempt,
            document_sha256=(self.digest,),
            send_available=False,
            provider_authenticated=False,
            envelope_sent=False,
            payload={
                "status": "created",
                "transactionId": self.attempt,
                "emailSubject": "Synthetic completion draft",
                "documents": [{
                    "documentId": "1",
                    "name": "Synthetic certificate",
                    "fileExtension": "pdf",
                    "documentBase64":
                        base64.b64encode(pdf).decode(),
                }],
                "recipients": {
                    "signers": [
                        {
                            "recipientId": "1",
                            "email": "first@example.invalid",
                            "name": "First synthetic signer",
                            "routingOrder": "1",
                        },
                        {
                            "recipientId": "2",
                            "email": "second@example.invalid",
                            "name": "Second synthetic signer",
                            "routingOrder": "2",
                        },
                    ]
                },
            },
        )

    def token(self):
        return "synthetic-token-not-a-secret"

    def test_request_uses_pinned_sandbox_host_and_account(self):
        request = prepare_sandbox_request(
            prepared=self.prepared, access_token=self.token()
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://demo.docusign.net/restapi/v2.1/accounts/"
            + self.account + "/envelopes",
        )
        self.assertEqual(
            json.loads(request.data)["status"], "created"
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer " + self.token(),
        )

    def test_successful_synthetic_draft_response_is_not_sent(self):
        seen = []
        def transport(request):
            seen.append(request)
            return FakeResponse({
                "envelopeId": self.envelope,
                "status": "created",
                "accountId": self.account,
            })

        result = simulate_sandbox_draft_post(
            prepared=self.prepared,
            access_token=self.token(),
            test_transport=transport,
        )

        self.assertEqual(len(seen), 1)
        self.assertEqual(
            result["provider_envelope_id"], self.envelope
        )
        self.assertFalse(result["envelope_sent"])
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["retry_allowed"])

    def test_without_test_transport_no_network_request(self):
        with self.assertRaises(ValidationError):
            simulate_sandbox_draft_post(
                prepared=self.prepared,
                access_token=self.token(),
            )

    def test_changed_pdf_rejected_before_transport(self):
        self.prepared.payload["documents"][0][
            "documentBase64"
        ] = base64.b64encode(b"%PDF-1.4\nchanged").decode()

        with self.assertRaises(ValidationError):
            prepare_sandbox_request(
                prepared=self.prepared, access_token=self.token()
            )

    def test_sent_status_rejected_before_transport(self):
        self.prepared.payload["status"] = "sent"
        with self.assertRaises(ValidationError):
            prepare_sandbox_request(
                prepared=self.prepared, access_token=self.token()
            )

    def test_mismatched_provider_account_rejected(self):
        with self.assertRaises(ValidationError):
            simulate_sandbox_draft_post(
                prepared=self.prepared,
                access_token=self.token(),
                test_transport=lambda req: FakeResponse({
                    "envelopeId": self.envelope,
                    "status": "created",
                    "accountId": str(uuid4()),
                }),
            )

    def test_unexpected_sent_response_does_not_authorize(self):
        with self.assertRaises(ValidationError):
            simulate_sandbox_draft_post(
                prepared=self.prepared,
                access_token=self.token(),
                test_transport=lambda req: FakeResponse({
                    "envelopeId": self.envelope,
                    "status": "sent",
                    "accountId": self.account,
                }),
            )

    def test_invalid_response_never_triggers_retry(self):
        calls = []
        def transport(request):
            calls.append(request)
            return FakeResponse(
                {"error": "synthetic failure"}, status=503
            )

        with self.assertRaises(ValidationError):
            simulate_sandbox_draft_post(
                prepared=self.prepared,
                access_token=self.token(),
                test_transport=transport,
            )

        self.assertEqual(len(calls), 1)

    def test_invalid_token_rejected(self):
        with self.assertRaises(ValidationError):
            prepare_sandbox_request(
                prepared=self.prepared,
                access_token="invalid\r\nHeader: value",
            )

    def test_unapproved_network_state_rejected(self):
        self.prepared.send_available = True
        with self.assertRaises(ValidationError):
            prepare_sandbox_request(
                prepared=self.prepared, access_token=self.token()
            )
