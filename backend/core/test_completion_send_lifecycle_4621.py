"""No-database security regression for the future send lifecycle."""
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .completion_send_authorization_4620 import ACTION
from .completion_send_lifecycle_4621 import (
    require_send_start_decision,
    require_provider_outcome_decision,
)


class SendLifecyclePolicyTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(),
            role=Role.SALES_MANAGER,
            is_authenticated=True,
            is_active=True,
        )
        msr_id = uuid4()
        project_id = uuid4()
        package_id = uuid4()
        self.project = SimpleNamespace(
            pk=project_id,
            current_approved_id=msr_id,
            state="ACTIVE",
        )
        self.msr = SimpleNamespace(
            pk=msr_id,
            project=self.project,
            status="APPROVED",
        )
        self.plan = SimpleNamespace(
            msr=self.msr,
            group="COMPLETION_FINANCED",
        )
        self.package = SimpleNamespace(
            pk=package_id,
            digest="a" * 64,
            plan=self.plan,
        )
        self.account = str(uuid4())
        self.attempt = SimpleNamespace(
            pk=uuid4(),
            release_package=self.package,
            initiated_by_id=uuid4(),
            provider_account_id=self.account,
            provider_envelope_id="",
            state="AUTH_PENDING",
            first_send_started_at=None,
        )
        self.manifest = SimpleNamespace(
            attempt_id=str(self.attempt.pk),
            project_id=str(project_id),
            release_package_id=str(package_id),
            document_sha256=("b" * 64,),
            recipient_ids=("1", "2"),
            signature_tabs_checked=True,
            signed_date_tabs_checked=True,
            ready_for_live_send=False,
            envelope_sent=False,
            completion_authorized=False,
        )
        self.payload = {
            "attempt_id": str(self.attempt.pk),
            "project_id": str(project_id),
            "approved_msr_id": str(msr_id),
            "release_package_id": str(package_id),
            "release_package_digest": "a" * 64,
            "provider_account_id": self.account,
            "authorizing_actor_id": str(self.actor.pk),
            "initiating_comptroller_id": str(
                self.attempt.initiated_by_id
            ),
            "certificate_group": "COMPLETION_FINANCED",
            "attempt_state": "AUTH_PENDING",
            "provider_envelope_id": "",
            "live_send_authorized": False,
            "email_sent": False,
            "provider_authenticated": False,
            "completion_authorized": False,
            "signature_tabs_checked": True,
            "signed_date_tabs_checked": True,
            "document_sha256": ["b" * 64],
            "recipient_ids": ["1", "2"],
        }
        self.event = SimpleNamespace(
            action=ACTION,
            actor_id=self.actor.pk,
            entity_id=project_id,
            payload=self.payload,
        )

    def start(self):
        return require_send_start_decision(
            actor=self.actor,
            attempt=self.attempt,
            authorization_event=self.event,
            manifest=self.manifest,
        )

    def test_valid_audit_allows_only_a_proposed_transition(self):
        decision = self.start()
        self.assertEqual(decision.next_state, "NETWORK_STARTED")
        self.assertTrue(decision.first_send_required)
        self.assertFalse(decision.network_request_permitted)
        self.assertFalse(decision.retry_allowed)
        self.assertEqual(self.attempt.state, "AUTH_PENDING")

    def test_ceo_role_allowed(self):
        self.actor.role = Role.CEO
        self.assertEqual(self.start().next_state, "NETWORK_STARTED")

    def test_comptroller_cannot_authorize_send(self):
        self.actor.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.start()

    def test_inactive_manager_rejected(self):
        self.actor.is_active = False
        with self.assertRaises(PermissionDenied):
            self.start()

    def test_changed_audit_actor_rejected(self):
        self.event.actor_id = uuid4()
        with self.assertRaises(ValidationError):
            self.start()

    def test_changed_release_digest_rejected(self):
        self.package.digest = "c" * 64
        with self.assertRaises(ValidationError):
            self.start()

    def test_changed_document_fingerprint_rejected(self):
        self.manifest.document_sha256 = ("d" * 64,)
        with self.assertRaises(ValidationError):
            self.start()

    def test_send_started_attempt_cannot_start_again(self):
        self.attempt.state = "NETWORK_STARTED"
        self.attempt.first_send_started_at = object()
        with self.assertRaises(ValidationError):
            self.start()

    def test_confirmed_response_requires_network_start(self):
        with self.assertRaises(ValidationError):
            require_provider_outcome_decision(
                attempt=self.attempt,
                outcome="CONFIRMED",
                provider_envelope_id=str(uuid4()),
            )

    def test_confirmed_response_records_identity_without_retry(self):
        self.attempt.state = "NETWORK_STARTED"
        self.attempt.first_send_started_at = object()
        envelope = str(uuid4())
        result = require_provider_outcome_decision(
            attempt=self.attempt,
            outcome="CONFIRMED",
            provider_envelope_id=envelope,
        )
        self.assertEqual(result.next_state, "SENT_UNCHECKED")
        self.assertEqual(result.provider_envelope_id, envelope)
        self.assertFalse(result.retry_allowed)
        self.assertFalse(result.completion_authorized)

    def test_uncertain_response_never_permits_resend(self):
        self.attempt.state = "NETWORK_STARTED"
        self.attempt.first_send_started_at = object()
        result = require_provider_outcome_decision(
            attempt=self.attempt,
            outcome="UNCERTAIN",
        )
        self.assertEqual(result.next_state, "SEND_UNCERTAIN")
        self.assertFalse(result.retry_allowed)
        self.assertFalse(result.network_request_permitted)

    def test_uncertain_response_cannot_claim_envelope_id(self):
        self.attempt.state = "NETWORK_STARTED"
        self.attempt.first_send_started_at = object()
        with self.assertRaises(ValidationError):
            require_provider_outcome_decision(
                attempt=self.attempt,
                outcome="UNCERTAIN",
                provider_envelope_id=str(uuid4()),
            )
