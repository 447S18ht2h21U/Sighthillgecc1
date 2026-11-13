"""Isolated database acceptance for dedicated completion sender OAuth."""
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_completion_send_transaction_4623 as fixtures
from . import docusign
from .completion_send_oauth_4627 import OPERATION, begin
from .models import DocusignChallenge, Role


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionSenderOAuthTests(TestCase):
    setUp = fixtures.IsolatedCompletionSendIntentTests.setUp
    manager = fixtures.IsolatedCompletionSendIntentTests.manager
    manifest = fixtures.IsolatedCompletionSendIntentTests.manifest
    create_authorization = (
        fixtures.IsolatedCompletionSendIntentTests.create_authorization
    )

    def start(self, actor, enabled="1", account=None):
        configuration = {
            "client_id": str(uuid4()),
            "account_id": (
                account if account is not None
                else self.attempt.provider_account_id
            ),
            "redirect_uri":
                "http://127.0.0.1:8000/api/docusign/callback/",
            "client_secret": "synthetic-test-secret",
            "blockers": [],
        }

        with patch.dict(
            "os.environ",
            {"GECC_TEST_COMPLETION_SEND_OAUTH": enabled},
        ), patch(
            "core.docusign.configuration",
            return_value=configuration,
        ), patch(
            "core.completion_send_oauth_4627."
            "prepare_completion_send_manifest",
            return_value=self.manifest(),
        ):
            return begin(
                actor=actor,
                attempt_id=self.attempt.pk,
                session_key="synthetic-session-key",
            )

    def test_sender_challenge_is_bound_without_sending(self):
        actor = self.manager()
        event = self.create_authorization(actor)
        result = self.start(actor)

        self.assertFalse(result["send_enabled"])
        self.assertFalse(result["envelope_sent"])
        self.assertFalse(result["provider_authenticated"])

        query = parse_qs(
            urlsplit(result["authorization_url"]).query
        )
        state = query["state"][0]
        self.assertEqual(len(state) >= 32, True)

        challenge = DocusignChallenge.objects.get(
            state_digest=docusign.digest(state)
        )

        self.assertEqual(challenge.actor_id, actor.pk)
        self.assertEqual(
            challenge.context["authorization_event_id"],
            str(event.pk),
        )
        self.assertEqual(
            challenge.context["completion_attempt_id"],
            str(self.attempt.pk),
        )
        self.assertEqual(
            challenge.context["operation"],
            OPERATION,
        )
        self.assertFalse(challenge.context["send_enabled"])

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")
        self.assertEqual(self.attempt.provider_envelope_id, "")

    def test_duplicate_challenge_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)
        self.start(actor)

        with self.assertRaises(ValidationError):
            self.start(actor)

        self.assertEqual(
            DocusignChallenge.objects.filter(
                context__operation=OPERATION
            ).count(),
            1,
        )

    def test_comptroller_cannot_initiate_sender_oauth(self):
        actor = self.manager()
        self.create_authorization(actor)

        with self.assertRaises(PermissionDenied):
            self.start(self.comptroller)

        self.assertFalse(
            DocusignChallenge.objects.filter(
                context__operation=OPERATION
            ).exists()
        )

    def test_wrong_sandbox_account_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)

        with self.assertRaises(ValidationError):
            self.start(actor, account=str(uuid4()))

        self.assertFalse(
            DocusignChallenge.objects.filter(
                context__operation=OPERATION
            ).exists()
        )

    def test_disabled_switch_prevents_challenge(self):
        actor = self.manager()
        self.create_authorization(actor)

        with self.assertRaises(ValidationError):
            self.start(actor, enabled="0")

        self.assertFalse(
            DocusignChallenge.objects.filter(
                context__operation=OPERATION
            ).exists()
        )

    def test_missing_prior_authorization_rejected(self):
        actor = self.manager()

        with self.assertRaises(ValidationError):
            self.start(actor)

        self.assertFalse(
            DocusignChallenge.objects.filter(
                context__operation=OPERATION
            ).exists()
        )
