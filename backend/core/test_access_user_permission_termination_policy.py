"""Security tests for the non-executable permission termination coordinator."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_grant_policy import (
    APPROVED, EXPIRED, REJECTED, REQUESTED, REVOKED,
)
from .access_user_permission_termination_policy import (
    ADMINISTRATIVE,
    EXPIRATION,
    SURRENDER,
    permission_termination_executed,
    proposed_termination_allowed,
)


class UserPermissionTerminationPolicyTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.administrator = uuid4()
        self.start = self.now - timedelta(days=1)
        self.end = self.now + timedelta(days=1)

    def check(self, action, **changes):
        values = {
            "action": action,
            "status": APPROVED,
            "recipient_id": self.recipient,
            "requested_by_id": self.requester,
            "actor_id": self.administrator,
            "actor_authenticated": True,
            "actor_active": True,
            "independently_authorized": True,
            "reason": "Documented termination reason.",
            "starts_at": self.start,
            "ends_at": self.end,
            "now": self.now,
        }
        values.update(changes)
        return proposed_termination_allowed(**values)

    def test_recipient_can_propose_voluntary_surrender(self):
        self.assertTrue(self.check(
            SURRENDER, actor_id=self.recipient
        ))

    def test_other_person_cannot_surrender_recipient_access(self):
        self.assertFalse(self.check(SURRENDER))
        self.assertFalse(self.check(
            SURRENDER, actor_id=self.requester
        ))

    def test_anonymous_or_inactive_surrender_denied(self):
        self.assertFalse(self.check(
            SURRENDER, actor_id=self.recipient,
            actor_authenticated=False,
        ))
        self.assertFalse(self.check(
            SURRENDER, actor_id=self.recipient,
            actor_active=False,
        ))

    def test_surrender_requires_reason(self):
        for reason in ("", " ", None):
            with self.subTest(reason=reason):
                self.assertFalse(self.check(
                    SURRENDER, actor_id=self.recipient,
                    reason=reason,
                ))

    def test_authorized_admin_revocation_agrees_with_transition(self):
        self.assertTrue(self.check(ADMINISTRATIVE))

    def test_admin_revocation_without_authority_denied(self):
        for authority in (False, None, "true", 1):
            with self.subTest(authority=authority):
                self.assertFalse(self.check(
                    ADMINISTRATIVE,
                    independently_authorized=authority,
                ))

    def test_recipient_requester_or_inactive_admin_denied(self):
        self.assertFalse(self.check(
            ADMINISTRATIVE, actor_id=self.recipient
        ))
        self.assertFalse(self.check(
            ADMINISTRATIVE, actor_id=self.requester
        ))
        self.assertFalse(self.check(
            ADMINISTRATIVE, actor_active=False
        ))
        self.assertFalse(self.check(
            ADMINISTRATIVE, actor_authenticated=False
        ))

    def test_admin_revocation_requires_meaningful_reason(self):
        for reason in ("", "  ", None):
            with self.subTest(reason=reason):
                self.assertFalse(self.check(
                    ADMINISTRATIVE, reason=reason
                ))

    def test_automatic_expiration_exact_boundary(self):
        self.assertFalse(self.check(EXPIRATION))
        self.assertTrue(self.check(
            EXPIRATION, now=self.end
        ))
        self.assertTrue(self.check(
            EXPIRATION, now=self.end + timedelta(seconds=1)
        ))

    def test_terminal_and_unapproved_states_denied(self):
        for status in (REQUESTED, REJECTED, REVOKED, EXPIRED):
            for action in (SURRENDER, ADMINISTRATIVE, EXPIRATION):
                with self.subTest(status=status, action=action):
                    self.assertFalse(self.check(
                        action, status=status,
                        actor_id=self.recipient
                        if action == SURRENDER else self.administrator,
                        now=self.end,
                    ))

    def test_unknown_action_denied(self):
        self.assertFalse(self.check("UNKNOWN_ACTION"))

    def test_live_execution_remains_disabled(self):
        self.assertTrue(self.check(
            SURRENDER, actor_id=self.recipient
        ))
        self.assertTrue(self.check(ADMINISTRATIVE))
        self.assertTrue(self.check(
            EXPIRATION, now=self.end
        ))
        self.assertFalse(permission_termination_executed(
            action=SURRENDER,
            recipient_id=self.recipient,
        ))