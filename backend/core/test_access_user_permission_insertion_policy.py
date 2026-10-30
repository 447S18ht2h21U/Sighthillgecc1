"""Tests for proposed permission insertion integrity.

These are structural policy tests, not database integrity tests.
No evidence is written, and no live permissions are activated.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_evidence_design import (
    PermissionRequestEvidence,
    PermissionDecisionEvidence,
    PermissionTerminationEvidence,
)
from .access_user_permission_insertion_policy import (
    insertion_requires_atomic_audit,
    insertion_requires_trusted_authorization,
    permission_insertion_executed,
    proposed_decision_insert_allowed,
    proposed_request_insert_allowed,
    proposed_termination_insert_allowed,
)


class UserPermissionInsertionPolicyTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()
        self.administrator = uuid4()

        self.request = PermissionRequestEvidence(
            request_id=uuid4(),
            recipient_id=self.recipient,
            requested_by_id=self.requester,
            permission_code="compensation.own.view",
            reason="Access required for personal compensation.",
            requested_at=self.now,
            starts_at=self.now + timedelta(hours=1),
            ends_at=self.now + timedelta(days=30),
        )

        self.decision = PermissionDecisionEvidence(
            request_id=self.request.request_id,
            decision_id=uuid4(),
            decided_by_id=self.approver,
            decision="APPROVED",
            decided_at=self.now + timedelta(minutes=5),
            reason="Independent approval.",
        )

        self.termination = PermissionTerminationEvidence(
            request_id=self.request.request_id,
            termination_id=uuid4(),
            terminated_by_id=self.administrator,
            termination_kind="ADMINISTRATIVE_REVOCATION",
            terminated_at=self.now + timedelta(days=2),
            reason="Permission no longer required.",
        )

    def request_allowed(self, **changes):
        values = {
            "request": self.request,
            "existing_decision": None,
            "existing_termination": None,
        }
        values.update(changes)
        return proposed_request_insert_allowed(**values)

    def decision_allowed(self, **changes):
        values = {
            "request": self.request,
            "decision": self.decision,
            "request_exists": True,
            "existing_decision": None,
        }
        values.update(changes)
        return proposed_decision_insert_allowed(**values)

    def termination_allowed(self, **changes):
        values = {
            "request": self.request,
            "decision": self.decision,
            "termination": self.termination,
            "request_exists": True,
            "decision_exists": True,
            "existing_termination": None,
        }
        values.update(changes)
        return proposed_termination_insert_allowed(**values)

    def test_valid_request_structure(self):
        self.assertTrue(self.request_allowed())

    def test_request_cannot_arrive_with_decision(self):
        self.assertFalse(self.request_allowed(
            existing_decision=self.decision
        ))

    def test_request_cannot_arrive_with_termination(self):
        self.assertFalse(self.request_allowed(
            existing_termination=self.termination
        ))

    def test_unknown_permission_or_invalid_window_denied(self):
        self.assertFalse(self.request_allowed(
            request=replace(
                self.request,
                permission_code="unknown.permission",
            )
        ))
        self.assertFalse(self.request_allowed(
            request=replace(
                self.request,
                ends_at=self.request.starts_at,
            )
        ))

    def test_valid_independent_decision_structure(self):
        self.assertTrue(self.decision_allowed())

    def test_decision_requires_existing_request(self):
        for exists in (False, None, 1, "true"):
            with self.subTest(exists=exists):
                self.assertFalse(self.decision_allowed(
                    request_exists=exists
                ))

    def test_duplicate_decision_denied(self):
        self.assertFalse(self.decision_allowed(
            existing_decision=self.decision
        ))

    def test_self_approval_and_requester_approval_denied(self):
        for actor in (self.recipient, self.requester):
            with self.subTest(actor=actor):
                self.assertFalse(self.decision_allowed(
                    decision=replace(
                        self.decision,
                        decided_by_id=actor,
                    )
                ))

    def test_mismatched_decision_request_denied(self):
        self.assertFalse(self.decision_allowed(
            decision=replace(
                self.decision,
                request_id=uuid4(),
            )
        ))

    def test_valid_termination_structure(self):
        self.assertTrue(self.termination_allowed())

    def test_termination_requires_both_records(self):
        self.assertFalse(self.termination_allowed(
            request_exists=False
        ))
        self.assertFalse(self.termination_allowed(
            decision_exists=False
        ))

    def test_duplicate_termination_denied(self):
        self.assertFalse(self.termination_allowed(
            existing_termination=self.termination
        ))

    def test_rejected_decision_cannot_be_terminated(self):
        self.assertFalse(self.termination_allowed(
            decision=replace(
                self.decision,
                decision="REJECTED",
            )
        ))

    def test_wrong_termination_request_denied(self):
        self.assertFalse(self.termination_allowed(
            termination=replace(
                self.termination,
                request_id=uuid4(),
            )
        ))

    def test_surrender_requires_recipient_identity(self):
        surrender = replace(
            self.termination,
            termination_kind="VOLUNTARY_SURRENDER",
            terminated_by_id=self.recipient,
        )
        self.assertTrue(self.termination_allowed(
            termination=surrender
        ))
        self.assertFalse(self.termination_allowed(
            termination=replace(
                surrender,
                terminated_by_id=self.administrator,
            )
        ))

    def test_automatic_expiration_requires_end_of_period(self):
        expired = replace(
            self.termination,
            termination_kind="AUTOMATIC_EXPIRATION",
            terminated_by_id=None,
            terminated_at=self.request.ends_at,
        )
        self.assertTrue(self.termination_allowed(
            termination=expired
        ))
        self.assertFalse(self.termination_allowed(
            termination=replace(
                expired,
                terminated_at=self.request.ends_at - timedelta(seconds=1),
            )
        ))

    def test_trusted_authorization_and_atomic_audit_required(self):
        self.assertTrue(insertion_requires_trusted_authorization())
        self.assertTrue(insertion_requires_atomic_audit())

    def test_live_insertion_remains_disabled(self):
        self.assertFalse(permission_insertion_executed(
            request=self.request,
            decision=self.decision,
            termination=self.termination,
        ))