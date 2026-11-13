"""Isolated sender OAuth API integration; no provider requests."""
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from . import docusign
from . import test_completion_send_oauth_4627 as fixtures
from .completion_send_oauth_4627 import OPERATION
from .models import DocusignChallenge, Role


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionSenderOAuthAPITests(TestCase):
    def setUp(self):
        fixtures.CompletionSenderOAuthTests.setUp(self)
        self.client = APIClient()
    manager = fixtures.CompletionSenderOAuthTests.manager
    manifest = fixtures.CompletionSenderOAuthTests.manifest
    create_authorization = (
        fixtures.CompletionSenderOAuthTests.create_authorization
    )

    def endpoint(self):
        return (
            "/api/completion-envelope-attempts/"
            + str(self.attempt.pk)
            + "/sender-oauth/"
        )

    def request_start(self, actor, *, enabled="1", account=None):
        self.client.force_login(actor)
        self.client.force_authenticate(user=actor)
        config = {
            "client_id": str(uuid4()),
            "account_id": (
                self.attempt.provider_account_id
                if account is None else account
            ),
            "redirect_uri":
                "http://127.0.0.1:8000/api/docusign/callback/",
            "client_secret": "synthetic-only",
            "blockers": [],
        }

        with patch.dict(
            "os.environ",
            {"GECC_TEST_COMPLETION_SEND_OAUTH": enabled},
        ), patch(
            "core.docusign.configuration",
            return_value=config,
        ), patch(
            "core.completion_send_oauth_4627."
            "prepare_completion_send_manifest",
            return_value=self.manifest(),
        ):
            return self.client.post(
                self.endpoint(),
                data={},
                content_type="application/json",
            )

    def challenges(self):
        return DocusignChallenge.objects.filter(
            context__operation=OPERATION
        )

    def test_manager_starts_bound_challenge_without_send(self):
        actor = self.manager()
        self.create_authorization(actor)
        response = self.request_start(actor)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["operation"], OPERATION)
        self.assertFalse(response.data["send_enabled"])
        self.assertFalse(response.data["provider_authenticated"])
        self.assertFalse(response.data["envelope_sent"])
        self.assertEqual(response["Cache-Control"], "private, no-store")

        state = parse_qs(
            urlsplit(response.data["authorization_url"]).query
        )["state"][0]
        challenge = DocusignChallenge.objects.get(
            state_digest=docusign.digest(state)
        )
        self.assertEqual(challenge.actor_id, actor.pk)
        self.assertEqual(
            challenge.context["completion_attempt_id"],
            str(self.attempt.pk),
        )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")
        self.assertEqual(self.attempt.provider_envelope_id, "")

    def test_disabled_endpoint_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)
        response = self.request_start(actor, enabled="0")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.challenges().exists())

    def test_comptroller_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)
        response = self.request_start(self.comptroller)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.challenges().exists())

    def test_missing_authorization_rejected(self):
        response = self.request_start(self.manager())
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.challenges().exists())

    def test_wrong_account_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)
        response = self.request_start(actor, account=str(uuid4()))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.challenges().exists())

    def test_duplicate_start_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)
        first = self.request_start(actor)
        second = self.request_start(actor)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(self.challenges().count(), 1)

    def test_get_does_not_initiate_oauth(self):
        actor = self.manager()
        self.client.force_login(actor)
        self.client.force_authenticate(user=actor)
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 405)
        self.assertFalse(self.challenges().exists())
