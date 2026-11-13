"""Disposable SQLite checks for completion-envelope lifecycle guards."""
from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from . import test_completion_retention_database_4616 as fixtures
from .completion_send_authorization_4620 import ACTION
from .models import AuditEvent, CompletionEnvelopeAttempt, Role, User
from .services import audit


class CompletionSendDatabaseTests(TestCase):
    setUp = fixtures.CompletionRetentionDatabaseTests.setUp

    def manager(self):
        actor = User.objects.filter(
            role=Role.SALES_MANAGER, is_active=True
        ).first()
        self.assertIsNotNone(actor)
        return actor

    def authorize_synthetic(self):
        actor = self.manager()
        audit(actor, ACTION, self.project.pk, {
            "attempt_id": str(self.attempt.pk),
            "provider_account_id": self.account,
            "release_package_id": str(self.package.pk),
            "release_package_digest": self.package.digest,
            "approved_msr_id": str(self.package.plan.msr_id),
            "project_id": str(self.project.pk),
            "initiating_comptroller_id": str(
                self.attempt.initiated_by_id
            ),
            "authorizing_actor_id": str(actor.pk),
            "attempt_state": "AUTH_PENDING",
            "live_send_authorized": False,
        })
        return actor

    def start_network(self):
        self.authorize_synthetic()
        started = timezone.now()
        count = CompletionEnvelopeAttempt.objects.filter(
            pk=self.attempt.pk, state="AUTH_PENDING"
        ).update(
            state="NETWORK_STARTED",
            first_send_started_at=started,
        )
        self.assertEqual(count, 1)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "NETWORK_STARTED")
        return started

    def test_wrong_release_authorization_cannot_start_network(self):
        actor = self.manager()
        audit(actor, ACTION, self.project.pk, {
            "attempt_id": str(self.attempt.pk),
            "provider_account_id": self.account,
            "release_package_id": str(uuid4()),
            "release_package_digest": self.package.digest,
            "approved_msr_id": str(self.package.plan.msr_id),
            "project_id": str(self.project.pk),
            "initiating_comptroller_id": str(
                self.attempt.initiated_by_id
            ),
            "authorizing_actor_id": str(actor.pk),
            "attempt_state": "AUTH_PENDING",
            "live_send_authorized": False,
        })

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="NETWORK_STARTED",
                    first_send_started_at=timezone.now(),
                )

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_wrong_project_authorization_cannot_start_network(self):
        actor = self.manager()
        audit(actor, ACTION, self.project.pk, {
            "attempt_id": str(self.attempt.pk),
            "provider_account_id": self.account,
            "release_package_id": str(self.package.pk),
            "release_package_digest": self.package.digest,
            "approved_msr_id": str(self.package.plan.msr_id),
            "project_id": str(uuid4()),
            "initiating_comptroller_id": str(
                self.attempt.initiated_by_id
            ),
            "authorizing_actor_id": str(actor.pk),
            "attempt_state": "AUTH_PENDING",
            "live_send_authorized": False,
        })

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="NETWORK_STARTED",
                    first_send_started_at=timezone.now(),
                )

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_wrong_comptroller_authorization_cannot_start_network(self):
        actor = self.manager()
        audit(actor, ACTION, self.project.pk, {
            "attempt_id": str(self.attempt.pk),
            "provider_account_id": self.account,
            "release_package_id": str(self.package.pk),
            "release_package_digest": self.package.digest,
            "approved_msr_id": str(self.package.plan.msr_id),
            "project_id": str(self.project.pk),
            "initiating_comptroller_id": str(uuid4()),
            "authorizing_actor_id": str(actor.pk),
            "attempt_state": "AUTH_PENDING",
            "live_send_authorized": False,
        })

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="NETWORK_STARTED",
                    first_send_started_at=timezone.now(),
                )

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_no_audit_cannot_start_network(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="NETWORK_STARTED",
                    first_send_started_at=timezone.now(),
                )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_audited_start_can_become_uncertain_but_not_retry(self):
        started = self.start_network()
        CompletionEnvelopeAttempt.objects.filter(
            pk=self.attempt.pk
        ).update(state="SEND_UNCERTAIN")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "SEND_UNCERTAIN")
        self.assertEqual(self.attempt.first_send_started_at, started)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(state="NETWORK_STARTED")

    def test_confirmed_envelope_identity_is_single_assignment(self):
        self.start_network()
        envelope = str(uuid4())

        CompletionEnvelopeAttempt.objects.filter(
            pk=self.attempt.pk
        ).update(
            state="SENT_UNCHECKED",
            provider_envelope_id=envelope,
        )

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "SENT_UNCHECKED")
        self.assertEqual(self.attempt.provider_envelope_id, envelope)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(provider_envelope_id=str(uuid4()))

    def test_unsent_cancellation_remains_permitted(self):
        CompletionEnvelopeAttempt.objects.filter(
            pk=self.attempt.pk
        ).update(state="CANCELLED_UNSENT")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "CANCELLED_UNSENT")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="NETWORK_STARTED",
                    first_send_started_at=timezone.now(),
                )

    def test_audit_cannot_authorize_second_network_start(self):
        self.start_network()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="NETWORK_STARTED",
                    first_send_started_at=timezone.now() + timedelta(seconds=1),
                )
