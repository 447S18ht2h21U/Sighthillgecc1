"""Regression requirements for historical permission approval independence.

The original approver's later account status must not rewrite valid
historical approval evidence. These tests do not authorize live access.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_grant_policy import (
    APPROVED,
    REVOKED,
    proposed_grant_is_current,
    proposed_grant_is_well_formed,
    permission_access_granted_by_policy,
)


class HistoricalPermissionApprovalTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()

        self.grant = {
            "permission_code": "compensation.own.view",
            "recipient_id": self.recipient,
            "requested_by_id": self.requester,
            "approved_by_id": self.approver,
            "status": APPROVED,
            "starts_at": self.now - timedelta(days=1),
            "ends_at": self.now + timedelta(days=1),
            "decided_at": self.now - timedelta(days=2),
            "revoked_at": None,
        }

    def eligible(self, **changes):
        values = {
            "valid_grant": proposed_grant_is_well_formed(**self.grant),
            "status": self.grant["status"],
            "starts_at": self.grant["starts_at"],
            "ends_at": self.grant["ends_at"],
            "now": self.now,
            "recipient_active": True,
            "approver_active": True,
        }
        values.update(changes)
        return proposed_grant_is_current(**values)

    def test_original_independent_approval_is_well_formed(self):
        self.assertTrue(proposed_grant_is_well_formed(**self.grant))
        self.assertTrue(self.eligible())

    def test_historical_approval_survives_approver_deactivation(self):
        self.assertTrue(self.eligible(approver_active=False))

    def test_inactive_recipient_still_loses_eligibility(self):
        self.assertFalse(self.eligible(recipient_active=False))
        self.assertFalse(self.eligible(
            recipient_active=False,
            approver_active=False,
        ))

    def test_approved_time_window_remains_enforced(self):
        self.assertFalse(self.eligible(now=self.grant["ends_at"]))
        self.assertFalse(self.eligible(
            now=self.grant["starts_at"] - timedelta(seconds=1),
        ))

    def test_invalid_or_revoked_approval_cannot_be_current(self):
        self.assertFalse(self.eligible(valid_grant=False))
        self.assertFalse(self.eligible(status=REVOKED))
        self.assertFalse(self.eligible(
            valid_grant=False,
            approver_active=False,
        ))

    def test_self_approval_remains_invalid(self):
        self_approved = {
            **self.grant,
            "approved_by_id": self.recipient,
        }
        self.assertFalse(
            proposed_grant_is_well_formed(**self_approved)
        )
        self.assertFalse(self.eligible(
            valid_grant=proposed_grant_is_well_formed(
                **self_approved
            ),
            approver_active=False,
        ))

    def test_live_access_remains_default_deny(self):
        self.assertFalse(permission_access_granted_by_policy(
            grant=self.grant,
            recipient_id=self.recipient,
            approver_active=False,
        ))