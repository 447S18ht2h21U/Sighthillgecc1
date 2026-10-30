"""Isolated policy tests for VERIDIAN permission-grant transitions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_grant_policy import (
    APPROVED, EXPIRED, REJECTED, REQUESTED, REVOKED,
)
from .access_user_permission_grant_transitions import (
    ALLOWED_TRANSITIONS,
    permission_transition_executed,
    transition_is_allowed,
)


class UserPermissionGrantTransitionTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.decision_actor = uuid4()

    def allowed(self, current, target, **changes):
        values = {
            "recipient_id": self.recipient,
            "requested_by_id": self.requester,
            "decision_actor_id": self.decision_actor,
            "decision_actor_active": True,
            "decision_at": self.now,
            "starts_at": self.now - timedelta(days=1),
            "ends_at": self.now + timedelta(days=1),
        }
        values.update(changes)
        return transition_is_allowed(current, target, **values)

    def test_request_can_be_approved_independently(self):
        self.assertTrue(self.allowed(REQUESTED, APPROVED))

    def test_request_can_be_rejected_independently(self):
        self.assertTrue(self.allowed(REQUESTED, REJECTED))

    def test_approved_permission_can_be_revoked(self):
        self.assertTrue(self.allowed(APPROVED, REVOKED))

    def test_approved_permission_expires_after_end(self):
        self.assertTrue(self.allowed(
            APPROVED, EXPIRED,
            decision_at=self.now + timedelta(days=1),
        ))

    def test_early_expiration_is_denied(self):
        self.assertFalse(self.allowed(APPROVED, EXPIRED))

    def test_revocation_after_end_is_denied_by_current_policy(self):
        self.assertFalse(self.allowed(
            APPROVED, REVOKED,
            decision_at=self.now + timedelta(days=2),
        ))

    def test_terminal_states_have_no_outgoing_transitions(self):
        for state in (REJECTED, REVOKED, EXPIRED):
            self.assertFalse(ALLOWED_TRANSITIONS[state])
            for target in ALLOWED_TRANSITIONS:
                with self.subTest(state=state, target=target):
                    self.assertFalse(self.allowed(state, target))

    def test_unlisted_transitions_are_denied(self):
        for current, target in (
            (REQUESTED, REVOKED),
            (REQUESTED, EXPIRED),
            (APPROVED, REQUESTED),
            (APPROVED, REJECTED),
            (REQUESTED, REQUESTED),
            (APPROVED, APPROVED),
            ("UNKNOWN", APPROVED),
        ):
            with self.subTest(current=current, target=target):
                self.assertFalse(self.allowed(current, target))

    def test_self_approval_and_requester_approval_denied(self):
        for actor in (self.recipient, self.requester, None):
            with self.subTest(actor=str(actor)):
                self.assertFalse(self.allowed(
                    REQUESTED, APPROVED,
                    decision_actor_id=actor,
                ))

    def test_inactive_decision_actor_denied(self):
        self.assertFalse(self.allowed(
            REQUESTED, APPROVED,
            decision_actor_active=False,
        ))

    def test_invalid_timestamps_and_windows_denied(self):
        naive = datetime(2026, 10, 26, 12)
        cases = (
            {"decision_at": naive},
            {"starts_at": naive},
            {"ends_at": naive},
            {"starts_at": self.now, "ends_at": self.now},
            {"starts_at": self.now + timedelta(days=2)},
            {"decision_at": None},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertFalse(self.allowed(
                    REQUESTED, APPROVED, **changes
                ))

    def test_execution_remains_disabled(self):
        self.assertTrue(self.allowed(REQUESTED, APPROVED))
        self.assertFalse(permission_transition_executed(
            current_status=REQUESTED,
            target_status=APPROVED,
            actor=self.decision_actor,
        ))