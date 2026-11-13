"""Database-backed sender identity to envelope handoff acceptance.

Uses disposable database records and a mocked OAuth provider.
Never contacts DocuSign, sends an envelope, or stores credentials.
"""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_completion_send_oauth_callback_4628 as fixtures
from .completion_provider_handoff_4631 import (
    prepare_verified_handoff,
)
from .models import (
    AuditEvent, CompletionEnvelopeAttempt, DocusignVerification,
)


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionVerifiedHandoffTests(TestCase):
    setUp = fixtures.CompletionSenderCallbackTests.setUp
    manager = fixtures.CompletionSenderCallbackTests.manager
    manifest = fixtures.CompletionSenderCallbackTests.manifest
    create_authorization = (
        fixtures.CompletionSenderCallbackTests.create_authorization
    )
    configuration = fixtures.CompletionSenderCallbackTests.configuration
    prepare = fixtures.CompletionSenderCallbackTests.prepare
    callback = fixtures.CompletionSenderCallbackTests.callback

    def verified(self):
        actor, config, state = self.prepare()
        result, requests = self.callback(actor, config, state)

        self.assertEqual(requests, 2)
        self.assertEqual(
            result["status"],
            "SANDBOX_SENDER_IDENTITY_VERIFIED_NO_SEND",
        )
        return actor, config, result["verification_id"]

    def handoff(
        self, actor, config, verification_id,
        *, enabled="1", prepared=None
    ):
        if prepared is None:
            prepared = SimpleNamespace(
                attempt_id=str(self.attempt.pk),
                account_id=self.attempt.provider_account_id,
                document_sha256=self.manifest().document_sha256,
                payload={
                    "recipients": {
                        "signers": [
                            {"recipientId": value}
                            for value in self.manifest().recipient_ids
                        ]
                    }
                },
                send_available=False,
                envelope_sent=False,
                provider_authenticated=False,
            )

        with patch.dict(
            "os.environ",
            {"GECC_TEST_COMPLETION_SEND_OAUTH": enabled},
        ), patch(
            "core.docusign.configuration",
            return_value=config,
        ), patch(
            "core.completion_provider_handoff_4631."
            "build_completion_envelope",
            return_value=prepared,
        ) as builder:
            try:
                return prepare_verified_handoff(
                    actor=actor,
                    attempt_id=self.attempt.pk,
                    verification_id=verification_id,
                )
            finally:
                self.assertLessEqual(builder.call_count, 1)

    def test_verified_sender_handoff_never_sends(self):
        actor, config, verification_id = self.verified()

        before_audit = AuditEvent.objects.count()
        result = self.handoff(actor, config, verification_id)

        self.assertTrue(result["oauth_identity_verified"])
        self.assertTrue(result["request_prepared_locally"])
        self.assertFalse(result["provider_request_executed"])
        self.assertFalse(result["envelope_sent"])
        self.assertFalse(result["completion_authorized"])
        self.assertFalse(result["retry_allowed"])
        self.assertEqual(
            result["verification_id"], str(verification_id)
        )
        self.assertEqual(AuditEvent.objects.count(), before_audit)

        attempt = CompletionEnvelopeAttempt.objects.get(
            pk=self.attempt.pk
        )
        self.assertEqual(attempt.state, "AUTH_PENDING")
        self.assertIsNone(attempt.first_send_started_at)
        self.assertEqual(attempt.provider_envelope_id, "")

    def test_comptroller_cannot_use_sender_proof(self):
        actor, config, verification_id = self.verified()

        with self.assertRaises(PermissionDenied):
            self.handoff(
                self.comptroller, config, verification_id
            )

    def test_changed_configured_account_rejected(self):
        actor, config, verification_id = self.verified()
        different = dict(config)
        different["account_id"] = str(uuid4())

        with self.assertRaises(ValidationError):
            self.handoff(actor, different, verification_id)

    def test_wrong_verification_identity_rejected(self):
        actor, config, verification_id = self.verified()

        with self.assertRaises(DocusignVerification.DoesNotExist):
            self.handoff(actor, config, str(uuid4()))

    def test_disabled_handoff_never_prepares_request(self):
        actor, config, verification_id = self.verified()

        with self.assertRaises(ValidationError):
            self.handoff(
                actor, config, verification_id, enabled="0"
            )

    def test_changed_recipient_binding_rejected(self):
        actor, config, verification_id = self.verified()

        changed = SimpleNamespace(
            attempt_id=str(self.attempt.pk),
            account_id=self.attempt.provider_account_id,
            document_sha256=self.manifest().document_sha256,
            payload={
                "recipients": {
                    "signers": [
                        {"recipientId": "unapproved-recipient"}
                    ]
                }
            },
            send_available=False,
            envelope_sent=False,
            provider_authenticated=False,
        )

        with self.assertRaises(ValidationError):
            self.handoff(
                actor, config, verification_id, prepared=changed
            )

    def test_changed_certificate_binding_rejected(self):
        actor, config, verification_id = self.verified()

        changed = SimpleNamespace(
            attempt_id=str(self.attempt.pk),
            account_id=self.attempt.provider_account_id,
            document_sha256=("0" * 64,),
            payload={
                "recipients": {
                    "signers": [
                        {"recipientId": value}
                        for value in self.manifest().recipient_ids
                    ]
                }
            },
            send_available=False,
            envelope_sent=False,
            provider_authenticated=False,
        )

        with self.assertRaises(ValidationError):
            self.handoff(
                actor, config, verification_id, prepared=changed
            )
