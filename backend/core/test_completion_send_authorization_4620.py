"""Disposable database checks for audited send authorization."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AuditEvent, Role, User
from . import test_completion_retention_database_4616 as retention_fixtures
from .completion_send_authorization_4620 import (
    ACTION,
    record_send_authorization,
)


@override_settings(ENVIRONMENT="development", DEBUG=True)
class SendAuthorizationDatabaseTests(TestCase):
    # Reuse the verified, unsent completion-attempt fixture.
    setUp = retention_fixtures.CompletionRetentionDatabaseTests.setUp

    def authorization_actor(self):
        actor = User.objects.filter(
            role=Role.SALES_MANAGER,
            is_active=True,
        ).first()
        self.assertIsNotNone(actor)
        self.assertNotEqual(actor.pk, self.comptroller.pk)
        return actor

    def record(self, *, actor=None, enabled="1"):
        selected = self.authorization_actor() if actor is None else actor

        gate = SimpleNamespace(
            attempt_id=str(self.attempt.pk),
            project_id=str(self.project.pk),
            release_package_id=str(self.package.pk),
            authority_validated=True,
            release_validated=True,
            live_sending_enabled=False,
            provider_authenticated=False,
            envelope_sent=False,
            completion_authorized=False,
        )

        manifest = SimpleNamespace(
            attempt_id=str(self.attempt.pk),
            project_id=str(self.project.pk),
            release_package_id=str(self.package.pk),
            document_sha256=("a" * 64,),
            recipient_ids=("1", "2"),
            signature_tabs_checked=True,
            signed_date_tabs_checked=True,
            ready_for_live_send=False,
            provider_authenticated=False,
            envelope_sent=False,
            completion_authorized=False,
        )

        # The source PDF/release fixture is synthetic; mock only
        # the prior gates whose separate unit suites already passed.
        # Assert actual authorization role independently below.
        with patch.dict(
            "os.environ",
            {"GECC_DEV_COMPLETION_SEND_AUTH_RECORD_ENABLED": enabled},
        ), patch(
            "core.completion_send_authorization_4620."
            "require_completion_send_preflight",
            return_value=gate,
        ), patch(
            "core.completion_send_authorization_4620."
            "prepare_completion_send_manifest",
            return_value=manifest,
        ):
            return record_send_authorization(
                actor=selected,
                attempt_id=self.attempt.pk,
            )

    def test_exact_authorization_is_audited_without_sending(self):
        result = self.record()
        event = AuditEvent.objects.get(
            pk=result["audit_event_id"]
        )

        self.assertEqual(event.action, ACTION)
        self.assertEqual(
            event.payload["attempt_id"],
            str(self.attempt.pk),
        )
        self.assertEqual(
            event.payload["release_package_digest"],
            self.package.digest,
        )
        self.assertFalse(event.payload["live_send_authorized"])
        self.assertFalse(event.payload["email_sent"])
        self.assertFalse(result["send_available"])
        self.assertFalse(result["completion_authorized"])

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")
        self.assertEqual(self.attempt.provider_envelope_id, "")
        self.assertIsNone(self.attempt.first_send_started_at)

    def test_second_authorization_is_rejected(self):
        self.record()

        with self.assertRaises(ValidationError):
            self.record()

        self.assertEqual(
            AuditEvent.objects.filter(action=ACTION).count(),
            1,
        )

    def test_disabled_recording_creates_no_audit_record(self):
        with self.assertRaises(ValidationError):
            self.record(enabled="0")

        self.assertFalse(
            AuditEvent.objects.filter(action=ACTION).exists()
        )

    def test_stale_attempt_does_not_create_audit_record(self):
        self.attempt.state = "CANCELLED_UNSENT"
        self.attempt.save(update_fields=["state"])

        with self.assertRaises(ValidationError):
            self.record()

        self.assertFalse(
            AuditEvent.objects.filter(action=ACTION).exists()
        )

    def test_comptroller_cannot_record_send_authorization(self):
        # Mocked downstream gates must never bypass this service's
        # independent role authorization.
        with self.assertRaises(PermissionDenied):
            self.record(actor=self.comptroller)

        self.assertFalse(
            AuditEvent.objects.filter(action=ACTION).exists()
        )

    def test_inactive_sales_manager_cannot_record_authorization(self):
        actor = self.authorization_actor()
        actor.is_active = False

        with self.assertRaises(PermissionDenied):
            self.record(actor=actor)

        self.assertFalse(
            AuditEvent.objects.filter(action=ACTION).exists()
        )

    def test_invalid_manifest_binding_is_rejected(self):
        actor = self.authorization_actor()

        incorrect_gate = SimpleNamespace(
            attempt_id="wrong-attempt",
            project_id=str(self.project.pk),
            release_package_id=str(self.package.pk),
            authority_validated=True,
            release_validated=True,
            live_sending_enabled=False,
            provider_authenticated=False,
            envelope_sent=False,
            completion_authorized=False,
        )

        with patch.dict(
            "os.environ",
            {"GECC_DEV_COMPLETION_SEND_AUTH_RECORD_ENABLED": "1"},
        ), patch(
            "core.completion_send_authorization_4620."
            "require_completion_send_preflight",
            return_value=incorrect_gate,
        ), patch(
            "core.completion_send_authorization_4620."
            "prepare_completion_send_manifest"
        ):
            with self.assertRaises(ValidationError):
                record_send_authorization(
                    actor=actor,
                    attempt_id=self.attempt.pk,
                )

        self.assertFalse(
            AuditEvent.objects.filter(action=ACTION).exists()
        )
