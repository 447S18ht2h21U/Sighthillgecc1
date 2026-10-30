"""Isolated tests for proposed permission revocation and expiration."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_grant_policy import (
    APPROVED,
    EXPIRED,
    REJECTED,
    REQUESTED,
    REVOKED,
)
from .access_user_permission_revocation_policy import (
    permission_revocation_executed,
    proposed_administrative_revocation_allowed,
    proposed_permission_effective_at,
    proposed_permission_is_time_expired,
    proposed_permission_surrender_allowed,
)


class UserPermissionRevocationPolicyTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.administrator = uuid4()
        self.start = self.now - timedelta(days=1)
        self.end = self.now + timedelta(days=1)

    def surrender(self, **changes):
        values = {
            "status": APPROVED,
            "recipient_id": self.recipient,
            "actor_id": self.recipient,
            "actor_authenticated": True,
            "actor_active": True,
            "reason": "I no longer need this access.",
        }
        values.update(changes)
        return proposed_permission_surrender_allowed(**values)

    def revoke(self, **changes):
        values = {
            "status": APPROVED,
            "recipient_id": self.recipient,
            "requested_by_id": self.requester,
            "actor_id": self.administrator,
            "actor_authenticated": True,
            "actor_active": True,
            "independently_authorized": True,
            "reason": "Access is no longer required.",
        }
        values.update(changes)
        return proposed_administrative_revocation_allowed(**values)

    def effective(self, **changes):
        values = {
            "status": APPROVED,
            "starts_at": self.start,
            "ends_at": self.end,
            "now": self.now,
            "recipient_active": True,
        }
        values.update(changes)
        return proposed_permission_effective_at(**values)

    def test_recipient_can_propose_voluntary_surrender(self):
        self.assertTrue(self.surrender())

    def test_other_person_cannot_surrender_recipient_access(self):
        self.assertFalse(self.surrender(actor_id=self.administrator))
        self.assertFalse(self.surrender(actor_id=None))

    def test_anonymous_or_inactive_surrender_denied(self):
        self.assertFalse(self.surrender(actor_authenticated=False))
        self.assertFalse(self.surrender(actor_active=False))

    def test_surrender_requires_meaningful_reason(self):
        for reason in ("", "  ", None):
            with self.subTest(reason=reason):
                self.assertFalse(self.surrender(reason=reason))

    def test_only_approved_state_can_be_surrendered(self):
        for status in (REQUESTED, REJECTED, REVOKED, EXPIRED):
            with self.subTest(status=status):
                self.assertFalse(self.surrender(status=status))

    def test_independently_authorized_administrator_qualifies(self):
        self.assertTrue(self.revoke())

    def test_revocation_denied_without_verified_authority(self):
        for authorized in (False, None, "true", 1):
            with self.subTest(authorized=authorized):
                self.assertFalse(
                    self.revoke(independently_authorized=authorized)
                )

    def test_recipient_requester_and_inactive_admin_denied(self):
        self.assertFalse(self.revoke(actor_id=self.recipient))
        self.assertFalse(self.revoke(actor_id=self.requester))
        self.assertFalse(self.revoke(actor_active=False))
        self.assertFalse(self.revoke(actor_authenticated=False))

    def test_administrative_revocation_requires_reason_and_approved_state(self):
        for reason in ("", "  ", None):
            with self.subTest(reason=reason):
                self.assertFalse(self.revoke(reason=reason))
        for status in (REQUESTED, REJECTED, REVOKED, EXPIRED):
            with self.subTest(status=status):
                self.assertFalse(self.revoke(status=status))

    def test_expiration_uses_exact_end_boundary(self):
        self.assertFalse(proposed_permission_is_time_expired(
            status=APPROVED, ends_at=self.end,
            now=self.end - timedelta(microseconds=1),
        ))
        self.assertTrue(proposed_permission_is_time_expired(
            status=APPROVED, ends_at=self.end, now=self.end,
        ))
        self.assertFalse(self.effective(now=self.end))
        self.assertTrue(self.effective(now=self.start))

    def test_invalid_or_terminal_grants_never_become_effective(self):
        for status in (REQUESTED, REJECTED, REVOKED, EXPIRED):
            with self.subTest(status=status):
                self.assertFalse(self.effective(status=status))
        self.assertFalse(self.effective(recipient_active=False))
        self.assertFalse(self.effective(now=self.start - timedelta(seconds=1)))
        self.assertFalse(self.effective(starts_at=self.end))
        self.assertFalse(self.effective(now=datetime(2026, 10, 26, 12)))

    def test_live_revocation_execution_remains_disabled(self):
        self.assertTrue(self.surrender())
        self.assertTrue(self.revoke())
        self.assertFalse(permission_revocation_executed(
            action="VOLUNTARY_SURRENDER",
            recipient_id=self.recipient,
        ))
        self.assertFalse(permission_revocation_executed(
            action="ADMINISTRATIVE_REVOCATION",
            recipient_id=self.recipient,
        ))