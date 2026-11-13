"""OAuth completion binding tests; no provider or database access."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .completion_provider_oauth_4611 import (
    OPERATION, begin, finish,
)


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionOAuthBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(),
            is_authenticated=True,
            is_active=True,
            role="COMPTROLLER",
        )
        self.attempt_id = str(uuid4())
        self.account = str(uuid4())
        self.envelope = str(uuid4())
        self.package_id = uuid4()
        self.project_id = uuid4()
        self.msr_id = uuid4()
        self.preview = {
            "documents": [{"documentId": "1", "name": "completion.pdf"}],
            "recipients": {"signers": []},
        }
        self.attempt = SimpleNamespace(
            pk=self.attempt_id,
            release_package_id=self.package_id,
            release_package=SimpleNamespace(
                digest="release-digest",
                plan=SimpleNamespace(
                    msr_id=self.msr_id,
                    msr=SimpleNamespace(project_id=self.project_id),
                ),
            ),
        )
        self.context = {
            "operation": OPERATION,
            "completion_attempt_id": self.attempt_id,
            "release_package_id": str(self.package_id),
            "release_package_digest": "release-digest",
            "project_id": str(self.project_id),
            "msr_id": str(self.msr_id),
            "account_id": self.account,
            "envelope_id": self.envelope,
        }
        self.challenge = SimpleNamespace(
            context=self.context,
            actor_id=self.actor.pk,
        )
        self.config = {"account_id": self.account}
        self.evidence = {
            "provider_response_validated": True,
            "completion_authorized": False,
            "project_completed": False,
            "completed_at": "2026-11-10T10:00:00+00:00",
            "pdf_manifest": [{"document_id": "1", "pdf_sha256": "a" * 64}],
        }

    def test_begin_requires_eligible_attempt_and_creates_read_challenge(self):
        with patch(
            "core.completion_provider_oauth_4611._eligible_attempt",
            return_value=(
                self.attempt, self.account, self.envelope, self.preview
            ),
        ), patch(
            "core.completion_provider_oauth_4611.docusign.configuration",
            return_value={"blockers": [], "account_id": self.account},
        ), patch(
            "core.completion_provider_oauth_4611.docusign.begin",
            return_value={
                "authorization_url": "https://account-d.docusign.com/oauth/auth",
                "expires_at": "2026-11-10T10:00:00+00:00",
            },
        ) as begin_mock:
            # Exercise the pure orchestration body under mocked dependencies.
            # The production entry point retains its transaction.atomic guard.
            result = begin.__wrapped__(self.actor, "session", self.attempt_id)

        self.assertFalse(result["send_available"])
        self.assertFalse(result["completion_authorized"])
        self.assertEqual(
            begin_mock.call_args.args[2]["operation"], OPERATION
        )
        self.assertEqual(
            begin_mock.call_args.args[2]["envelope_id"], self.envelope
        )

    def test_finish_accepts_bound_response_without_completion_authority(self):
        with patch(
            "core.completion_provider_oauth_4611._eligible_attempt",
            return_value=(
                self.attempt, self.account, self.envelope, self.preview
            ),
        ), patch(
            "core.completion_provider_oauth_4611.read_completed_certificate",
            return_value=self.evidence,
        ) as reader:
            result = finish(
                self.actor, self.challenge, self.config, "sandbox-token"
            )

        self.assertTrue(result["oauth_callback_binding_verified"])
        self.assertFalse(result["signed_documents_retained"])
        self.assertFalse(result["completion_authorized"])
        self.assertFalse(result["project_completed"])
        reader.assert_called_once()

    def test_changed_envelope_rejected_before_provider_read(self):
        context = {**self.context, "envelope_id": str(uuid4())}
        challenge = SimpleNamespace(
            context=context,
            actor_id=self.actor.pk,
        )

        with patch(
            "core.completion_provider_oauth_4611._eligible_attempt",
            return_value=(
                self.attempt, self.account, self.envelope, self.preview
            ),
        ), patch(
            "core.completion_provider_oauth_4611.read_completed_certificate",
        ) as reader:
            with self.assertRaises(ValidationError):
                finish(self.actor, challenge, self.config, "token")
            reader.assert_not_called()

    def test_wrong_actor_rejected(self):
        challenge = SimpleNamespace(
            context=self.context,
            actor_id=uuid4(),
        )
        with self.assertRaises(PermissionDenied):
            finish(self.actor, challenge, self.config, "token")

    def test_wrong_account_rejected(self):
        with patch(
            "core.completion_provider_oauth_4611._eligible_attempt",
            return_value=(
                self.attempt, self.account, self.envelope, self.preview
            ),
        ), patch(
            "core.completion_provider_oauth_4611.read_completed_certificate",
        ) as reader:
            with self.assertRaises(ValidationError):
                finish(
                    self.actor,
                    self.challenge,
                    {"account_id": str(uuid4())},
                    "token",
                )
            reader.assert_not_called()

    def test_provider_cannot_claim_completion_authority(self):
        forged = {**self.evidence, "completion_authorized": True}
        with patch(
            "core.completion_provider_oauth_4611._eligible_attempt",
            return_value=(
                self.attempt, self.account, self.envelope, self.preview
            ),
        ), patch(
            "core.completion_provider_oauth_4611.read_completed_certificate",
            return_value=forged,
        ):
            with self.assertRaises(ValidationError):
                finish(
                    self.actor, self.challenge, self.config, "token"
                )
