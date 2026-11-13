"""Disposable sender OAuth callback integration acceptance."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign
from . import test_completion_send_oauth_4627 as fixtures
from .completion_send_oauth_4627 import begin
from .completion_send_oauth_callback_4628 import (
    is_sender_state, finish,
)
from .models import DocusignChallenge, DocusignVerification


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionSenderCallbackTests(TestCase):
    setUp = fixtures.CompletionSenderOAuthTests.setUp
    manager = fixtures.CompletionSenderOAuthTests.manager
    manifest = fixtures.CompletionSenderOAuthTests.manifest
    create_authorization = (
        fixtures.CompletionSenderOAuthTests.create_authorization
    )

    def configuration(self):
        return {
            "client_id": str(uuid4()),
            "account_id": self.attempt.provider_account_id,
            "redirect_uri":
                "http://127.0.0.1:8000/api/docusign/callback/",
            "client_secret": "synthetic-secret",
            "blockers": [],
        }

    def prepare(self):
        actor = self.manager()
        self.create_authorization(actor)
        config = self.configuration()

        with patch.dict(
            "os.environ", {"GECC_TEST_COMPLETION_SEND_OAUTH": "1"}
        ), patch(
            "core.docusign.configuration", return_value=config
        ), patch(
            "core.completion_send_oauth_4627."
            "prepare_completion_send_manifest",
            return_value=self.manifest()
        ):
            result = begin(
                actor=actor,
                attempt_id=self.attempt.pk,
                session_key="synthetic-session-key",
            )

        state = parse_qs(
            urlsplit(result["authorization_url"]).query
        )["state"][0]

        return actor, config, state

    def callback(self, actor, config, state, *,
                 session="synthetic-session-key",
                 account=None, enabled="1"):
        def provider(path, authorization, data=None):
            if path == "/oauth/token":
                return {
                    "access_token": "synthetic-access-token",
                    "token_type": "Bearer",
                    "expires_in": 300,
                }

            if path == "/oauth/userinfo":
                return {
                    "sub": str(uuid4()),
                    "accounts": [{
                        "account_id": (
                            account if account is not None
                            else config["account_id"]
                        ),
                        "base_uri": docusign.BASE_URI,
                    }],
                }

            raise AssertionError("Unexpected OAuth operation.")

        with patch.dict(
            "os.environ",
            {"GECC_TEST_COMPLETION_SEND_OAUTH": enabled},
        ), patch(
            "core.docusign.configuration", return_value=config
        ), patch(
            "core.docusign.request_json", side_effect=provider
        ) as network, patch(
            "core.completion_send_oauth_callback_4628."
            "prepare_completion_send_manifest",
            return_value=self.manifest()
        ):
            result = finish(
                actor=actor,
                session_key=session,
                state=state,
                code="synthetic-authorization-code",
            )
            return result, network.call_count

    def test_identity_verified_without_envelope_send(self):
        actor, config, state = self.prepare()
        self.assertTrue(is_sender_state(state))

        result, requests = self.callback(actor, config, state)

        self.assertEqual(requests, 2)
        self.assertEqual(
            result["status"],
            "SANDBOX_SENDER_IDENTITY_VERIFIED_NO_SEND",
        )
        self.assertFalse(result["send_enabled"])
        self.assertFalse(result["envelope_sent"])

        challenge = DocusignChallenge.objects.get(
            state_digest=docusign.digest(state)
        )
        self.assertIsNotNone(challenge.consumed_at)

        proof = DocusignVerification.objects.get(
            pk=result["verification_id"]
        )
        self.assertFalse(proof.identity["tokens_retained"])
        self.assertFalse(proof.identity["envelope_sent"])
        self.assertNotIn("access_token", proof.identity)
        self.assertNotIn("refresh_token", proof.identity)

    def test_oauth_state_cannot_be_replayed(self):
        actor, config, state = self.prepare()
        self.callback(actor, config, state)

        with self.assertRaises(ValidationError):
            self.callback(actor, config, state)

    def test_other_manager_cannot_consume_challenge(self):
        actor, config, state = self.prepare()
        other = self.comptroller

        with self.assertRaises(PermissionDenied):
            self.callback(other, config, state)

        challenge = DocusignChallenge.objects.get(
            state_digest=docusign.digest(state)
        )
        self.assertIsNone(challenge.consumed_at)

    def test_wrong_session_cannot_consume_challenge(self):
        actor, config, state = self.prepare()

        with self.assertRaises(ValidationError):
            self.callback(
                actor, config, state, session="wrong-session"
            )

    def test_wrong_account_rejected_after_consumption(self):
        actor, config, state = self.prepare()

        with self.assertRaises(ValidationError):
            self.callback(
                actor, config, state, account=str(uuid4())
            )

        self.assertFalse(
            DocusignVerification.objects.filter(
                actor=actor,
                identity__purpose=
                    "SANDBOX_COMPLETION_SENDER_IDENTITY_ONLY",
            ).exists()
        )

    def test_disabled_callback_never_consumes_challenge(self):
        actor, config, state = self.prepare()

        with self.assertRaises(ValidationError):
            self.callback(actor, config, state, enabled="0")

        challenge = DocusignChallenge.objects.get(
            state_digest=docusign.digest(state)
        )
        self.assertIsNone(challenge.consumed_at)
