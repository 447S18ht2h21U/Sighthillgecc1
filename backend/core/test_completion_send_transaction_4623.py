"""Disposable integration of audit authorization and send-intent state."""
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from . import test_completion_retention_database_4616 as fixtures
from .completion_send_authorization_4620 import ACTION
from .completion_send_transaction_4623 import (
    reserve_isolated_send_intent,
)
from .documents import canonical_hash
from .models import AuditEvent, CompletionEnvelopeAttempt, Role, User
from .services import audit


@override_settings(ENVIRONMENT="development", DEBUG=True)
class IsolatedCompletionSendIntentTests(TestCase):
    setUp = fixtures.CompletionRetentionDatabaseTests.setUp

    def manager(self):
        actor = User.objects.filter(
            role=Role.SALES_MANAGER,
            is_active=True,
        ).first()
        self.assertIsNotNone(actor)
        return actor

    def manifest(self):
        return SimpleNamespace(
            attempt_id=str(self.attempt.pk),
            project_id=str(self.project.pk),
            release_package_id=str(self.package.pk),
            document_sha256=("a" * 64,),
            recipient_ids=("1", "2"),
            signature_tabs_checked=True,
            signed_date_tabs_checked=True,
            ready_for_live_send=False,
            envelope_sent=False,
            completion_authorized=False,
        )

    def create_authorization(self, actor, *, corrupt=False):
        manifest = self.manifest()
        payload = {
            "schema_version": 1,
            "attempt_id": str(self.attempt.pk),
            "project_id": str(self.project.pk),
            "approved_msr_id": str(self.package.plan.msr_id),
            "release_package_id": str(self.package.pk),
            "release_package_digest": self.package.digest,
            "provider_account_id": self.attempt.provider_account_id,
            "authorizing_actor_id": str(actor.pk),
            "initiating_comptroller_id": str(
                self.attempt.initiated_by_id
            ),
            "certificate_group": self.package.plan.group,
            "document_sha256": list(manifest.document_sha256),
            "recipient_ids": list(manifest.recipient_ids),
            "signature_tabs_checked": True,
            "signed_date_tabs_checked": True,
            "attempt_state": "AUTH_PENDING",
            "provider_envelope_id": "",
            "live_send_authorized": False,
            "email_sent": False,
            "provider_authenticated": False,
            "completion_authorized": False,
        }
        payload["manifest_binding_sha256"] = canonical_hash(payload)

        if corrupt:
            payload["manifest_binding_sha256"] = "0" * 64

        return audit(actor, ACTION, self.project.pk, payload)

    def reserve(self, actor, *, enabled="1"):
        with patch.dict(
            "os.environ",
            {"GECC_TEST_COMPLETION_SEND_INTENT": enabled},
        ), patch(
            "core.completion_send_transaction_4623."
            "prepare_completion_send_manifest",
            return_value=self.manifest(),
        ):
            return reserve_isolated_send_intent(
                actor=actor,
                attempt_id=self.attempt.pk,
            )

    def test_durable_audit_allows_one_isolated_reservation(self):
        actor = self.manager()
        self.create_authorization(actor)

        result = self.reserve(actor)

        self.assertEqual(result["state"], "NETWORK_STARTED")
        self.assertFalse(result["network_request_permitted"])
        self.assertFalse(result["retry_allowed"])
        self.assertFalse(result["completion_authorized"])

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "NETWORK_STARTED")
        self.assertIsNotNone(self.attempt.first_send_started_at)
        self.assertEqual(self.attempt.provider_envelope_id, "")

        self.assertEqual(
            AuditEvent.objects.filter(
                action="completion_envelope."
                       "isolated_send_intent_reserved"
            ).count(),
            1,
        )

    def test_missing_authorization_prevents_transition(self):
        actor = self.manager()

        with self.assertRaises(ValidationError):
            self.reserve(actor)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_tampered_manifest_digest_prevents_transition(self):
        actor = self.manager()
        self.create_authorization(actor, corrupt=True)

        with self.assertRaises(ValidationError):
            self.reserve(actor)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_disabled_switch_prevents_transition(self):
        actor = self.manager()
        self.create_authorization(actor)

        with self.assertRaises(ValidationError):
            self.reserve(actor, enabled="0")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_comptroller_cannot_reserve_send(self):
        actor = self.manager()
        self.create_authorization(actor)

        with self.assertRaises(Exception):
            self.reserve(self.comptroller)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_repeat_reservation_is_rejected(self):
        actor = self.manager()
        self.create_authorization(actor)
        self.reserve(actor)

        with self.assertRaises(ValidationError):
            self.reserve(actor)

        self.assertEqual(
            AuditEvent.objects.filter(
                action="completion_envelope."
                       "isolated_send_intent_reserved"
            ).count(),
            1,
        )
