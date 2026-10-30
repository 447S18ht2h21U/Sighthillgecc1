"""Consistency tests for non-executable VERIDIAN permission policies."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_grant_policy import (
    APPROVED,
    EXPIRED,
    REJECTED,
    REQUESTED,
    REVOKED,
    permission_access_granted_by_policy,
)
from .access_user_permission_grant_transitions import (
    permission_transition_executed,
    transition_is_allowed,
)
from .access_user_permission_revocation_policy import (
    permission_revocation_executed,
    proposed_administrative_revocation_allowed,
    proposed_permission_effective_at,
    proposed_permission_is_time_expired,
    proposed_permission_surrender_allowed,
)


class UserPermissionPolicyConsistencyTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()
        self.administrator = uuid4()
        self.starts_at = self.now - timedelta(days=1)
        self.ends_at = self.now + timedelta(days=1)

    def transition(self, actor, current, target, at=None):
        return transition_is_allowed(
            current,
            target,
            recipient_id=self.recipient,
            requested_by_id=self.requester,
            decision_actor_id=actor,
            decision_actor_active=True,
            decision_at=self.now if at is None else at,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
        )

    def test_independent_approval_consistent(self):
        self.assertTrue(self.transition(
            self.approver, REQUESTED, APPROVED
        ))
        self.assertFalse(self.transition(
            self.recipient, REQUESTED, APPROVED
        ))
        self.assertFalse(self.transition(
            self.requester, REQUESTED, APPROVED
        ))

    def test_independent_rejection_consistent(self):
        self.assertTrue(self.transition(
            self.approver, REQUESTED, REJECTED
        ))
        self.assertFalse(self.transition(
            self.recipient, REQUESTED, REJECTED
        ))
        self.assertFalse(self.transition(
            self.requester, REQUESTED, REJECTED
        ))

    def test_administrative_revocation_matches_transition(self):
        policy_allowed = proposed_administrative_revocation_allowed(
            status=APPROVED,
            recipient_id=self.recipient,
            requested_by_id=self.requester,
            actor_id=self.administrator,
            actor_authenticated=True,
            actor_active=True,
            independently_authorized=True,
            reason="Authorized access removal.",
        )
        self.assertTrue(policy_allowed)
        self.assertTrue(self.transition(
            self.administrator, APPROVED, REVOKED
        ))

    def test_unauthorized_administrative_revocation_denied(self):
        self.assertFalse(
            proposed_administrative_revocation_allowed(
                status=APPROVED,
                recipient_id=self.recipient,
                requested_by_id=self.requester,
                actor_id=self.administrator,
                actor_authenticated=True,
                actor_active=True,
                independently_authorized=False,
                reason="Unauthorized removal.",
            )
        )

    def test_voluntary_surrender_is_not_yet_transition_compatible(self):
        self.assertTrue(proposed_permission_surrender_allowed(
            status=APPROVED,
            recipient_id=self.recipient,
            actor_id=self.recipient,
            actor_authenticated=True,
            actor_active=True,
            reason="I no longer need access.",
        ))
        self.assertFalse(self.transition(
            self.recipient, APPROVED, REVOKED
        ))

    def test_expiration_is_automatic_at_end(self):
        self.assertTrue(proposed_permission_is_time_expired(
            status=APPROVED,
            ends_at=self.ends_at,
            now=self.ends_at,
        ))
        self.assertFalse(proposed_permission_effective_at(
            status=APPROVED,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            now=self.ends_at,
            recipient_active=True,
        ))

    def test_approved_to_expired_transition_follows_time(self):
        self.assertFalse(self.transition(
            self.administrator, APPROVED, EXPIRED
        ))
        self.assertTrue(self.transition(
            self.administrator, APPROVED, EXPIRED,
            at=self.ends_at,
        ))

    def test_terminal_states_do_not_reactivate(self):
        for state in (REJECTED, REVOKED, EXPIRED):
            with self.subTest(status=state):
                self.assertFalse(self.transition(
                    self.administrator, state, APPROVED
                ))
                self.assertFalse(proposed_permission_effective_at(
                    status=state,
                    starts_at=self.starts_at,
                    ends_at=self.ends_at,
                    now=self.now,
                    recipient_active=True,
                ))

    def test_expiration_does_not_require_database_status_update(self):
        self.assertFalse(proposed_permission_effective_at(
            status=APPROVED,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            now=self.ends_at + timedelta(seconds=1),
            recipient_active=True,
        ))

    def test_all_live_execution_paths_default_deny(self):
        self.assertFalse(permission_access_granted_by_policy())
        self.assertFalse(permission_transition_executed())
        self.assertFalse(permission_revocation_executed())