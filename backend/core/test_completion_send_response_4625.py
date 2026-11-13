"""Disposable database regression for synthetic provider responses."""
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_completion_send_transaction_4623 as fixtures
from .completion_send_response_4625 import (
    RESPONSE_ACTION, record_isolated_response,
)
from .models import AuditEvent, CompletionEnvelopeAttempt


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionSendResponseTests(TestCase):
    setUp = fixtures.IsolatedCompletionSendIntentTests.setUp
    manager = fixtures.IsolatedCompletionSendIntentTests.manager
    manifest = fixtures.IsolatedCompletionSendIntentTests.manifest
    create_authorization = (
        fixtures.IsolatedCompletionSendIntentTests.create_authorization
    )
    reserve = fixtures.IsolatedCompletionSendIntentTests.reserve

    def prepare(self):
        actor = self.manager()
        self.create_authorization(actor)
        self.reserve(actor)
        return actor

    def respond(self, actor, outcome, envelope=None, enabled="1"):
        with patch.dict(
            "os.environ",
            {"GECC_TEST_COMPLETION_SEND_INTENT": enabled},
        ):
            return record_isolated_response(
                actor=actor,
                attempt_id=self.attempt.pk,
                outcome=outcome,
                provider_envelope_id=envelope,
            )

    def assert_one_response(self):
        self.assertEqual(
            AuditEvent.objects.filter(action=RESPONSE_ACTION).count(), 1
        )

    def test_confirmed_synthetic_result_single_assignment(self):
        actor = self.prepare()
        envelope = str(uuid4())
        result = self.respond(actor, "CONFIRMED", envelope)

        self.assertEqual(result["state"], "SENT_UNCHECKED")
        self.assertEqual(result["provider_envelope_id"], envelope)
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["completion_authorized"])
        self.assertFalse(result["retry_allowed"])

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.provider_envelope_id, envelope)
        self.assertIsNotNone(self.attempt.first_send_started_at)
        self.assert_one_response()

    def test_uncertain_result_has_no_envelope_or_retry(self):
        actor = self.prepare()
        result = self.respond(actor, "UNCERTAIN")

        self.assertEqual(result["state"], "SEND_UNCERTAIN")
        self.assertEqual(result["provider_envelope_id"], "")
        self.assertFalse(result["retry_allowed"])

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "SEND_UNCERTAIN")
        self.assert_one_response()

    def test_second_response_rejected(self):
        actor = self.prepare()
        self.respond(actor, "UNCERTAIN")

        with self.assertRaises(ValidationError):
            self.respond(actor, "CONFIRMED", str(uuid4()))

        self.assert_one_response()

    def test_no_send_intent_rejects_response(self):
        actor = self.manager()

        with self.assertRaises(ValidationError):
            self.respond(actor, "CONFIRMED", str(uuid4()))

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_disabled_switch_rejects_response(self):
        actor = self.prepare()

        with self.assertRaises(ValidationError):
            self.respond(actor, "UNCERTAIN", enabled="0")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "NETWORK_STARTED")

    def test_comptroller_cannot_record_sending_response(self):
        self.prepare()

        with self.assertRaises(PermissionDenied):
            self.respond(self.comptroller, "UNCERTAIN")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "NETWORK_STARTED")
