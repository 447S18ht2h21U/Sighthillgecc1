"""Isolated security tests for the proposed user-permission grant policy."""

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
    proposed_grant_is_current,
    proposed_grant_is_well_formed,
)


class UserPermissionGrantPolicyTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()

    def grant(self, **overrides):
        values = {
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
        values.update(overrides)
        return values

    def current(self, grant, **overrides):
        values = {
            "valid_grant": proposed_grant_is_well_formed(**grant),
            "status": grant["status"],
            "starts_at": grant["starts_at"],
            "ends_at": grant["ends_at"],
            "now": self.now,
            "recipient_active": True,
            "approver_active": True,
        }
        values.update(overrides)
        return proposed_grant_is_current(**values)

    def test_valid_independently_approved_proposal(self):
        grant = self.grant()
        self.assertTrue(proposed_grant_is_well_formed(**grant))
        self.assertTrue(self.current(grant))

    def test_unknown_permission_denied(self):
        grant = self.grant(permission_code="unknown.permission")
        self.assertFalse(proposed_grant_is_well_formed(**grant))
        self.assertFalse(self.current(grant))

    def test_self_request_allowed_but_self_approval_denied(self):
        grant = self.grant(requested_by_id=self.recipient)
        self.assertTrue(proposed_grant_is_well_formed(**grant))
        self.assertTrue(self.current(grant))

        self_approved = self.grant(
            requested_by_id=self.recipient,
            approved_by_id=self.recipient,
        )
        self.assertFalse(
            proposed_grant_is_well_formed(**self_approved)
        )
        self.assertFalse(self.current(self_approved))

        requested = self.grant(
            requested_by_id=self.recipient,
            approved_by_id=None,
            decided_at=None,
            status=REQUESTED,
        )
        self.assertTrue(proposed_grant_is_well_formed(**requested))
        self.assertFalse(self.current(requested))

    def test_approval_must_be_independent(self):
        for approver in (None, self.recipient, self.requester):
            with self.subTest(approver=str(approver)):
                grant = self.grant(approved_by_id=approver)
                self.assertFalse(proposed_grant_is_well_formed(**grant))

    def test_requested_state_has_no_approval_evidence(self):
        valid = self.grant(
            status=REQUESTED,
            approved_by_id=None,
            decided_at=None,
        )
        self.assertTrue(proposed_grant_is_well_formed(**valid))
        self.assertFalse(self.current(valid))

        invalid = self.grant(
            status=REQUESTED,
            approved_by_id=self.approver,
        )
        self.assertFalse(proposed_grant_is_well_formed(**invalid))

    def test_rejected_and_expired_states_not_current(self):
        for state in (REJECTED, EXPIRED):
            with self.subTest(state=state):
                grant = self.grant(status=state)
                self.assertTrue(proposed_grant_is_well_formed(**grant))
                self.assertFalse(self.current(grant))

    def test_revoked_requires_valid_evidence(self):
        valid = self.grant(
            status=REVOKED,
            revoked_at=self.now,
        )
        self.assertTrue(proposed_grant_is_well_formed(**valid))
        self.assertFalse(self.current(valid))

        invalid = self.grant(
            status=REVOKED,
            revoked_at=None,
        )
        self.assertFalse(proposed_grant_is_well_formed(**invalid))

    def test_invalid_effective_period_denied(self):
        cases = (
            self.grant(ends_at=self.now - timedelta(days=2)),
            self.grant(starts_at=self.now + timedelta(days=1)),
            self.grant(starts_at=self.now, ends_at=self.now),
        )
        for grant in cases:
            with self.subTest(grant=grant):
                self.assertFalse(self.current(grant))

    def test_expired_and_future_windows_denied(self):
        expired = self.grant(
            starts_at=self.now - timedelta(days=3),
            ends_at=self.now - timedelta(days=1),
        )
        future = self.grant(
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=3),
        )
        self.assertFalse(self.current(expired))
        self.assertFalse(self.current(future))

    def test_inactive_recipient_denied_historical_approver_independent(self):
        grant = self.grant()
        self.assertFalse(self.current(grant, recipient_active=False))
        self.assertTrue(self.current(grant, approver_active=False))
        self.assertFalse(self.current(
            grant,
            recipient_active=False,
            approver_active=False,
        ))

    def test_naive_timestamps_denied(self):
        naive = datetime(2026, 10, 26, 12, 0)
        grant = self.grant(starts_at=naive)
        self.assertFalse(proposed_grant_is_well_formed(**grant))

        valid = self.grant()
        self.assertFalse(self.current(valid, now=naive))

    def test_live_permission_evaluation_always_denies(self):
        grant = self.grant()
        self.assertTrue(self.current(grant))

        self.assertFalse(
            permission_access_granted_by_policy(
                grant=grant,
                actor=self.recipient,
                now=self.now,
            )
        )