"""Security tests for non-operational MSR approval evidence."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_msr_delegation_approval_evidence import (
    APPROVED, EXPIRED, REJECTED, REQUESTED, REVOKED,
    MSRDelegationApprovalEvidence,
    msr_approval_evidence_grants_access,
    proposed_approval_is_current,
    validate_approval_evidence,
)


class MSRDelegationApprovalEvidenceTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        self.request_id = uuid4()
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()
        self.project = uuid4()

    def evidence(self, **changes):
        values = {
            "request_id": self.request_id,
            "recipient_id": self.recipient,
            "requested_by_id": self.requester,
            "approved_by_id": self.approver,
            "project_ids": (self.project,),
            "starts_at": self.now - timedelta(hours=1),
            "ends_at": self.now + timedelta(days=1),
            "status": APPROVED,
            "decided_at": self.now - timedelta(minutes=30),
            "revoked_at": None,
        }
        values.update(changes)
        return MSRDelegationApprovalEvidence(**values)

    def test_valid_approval_evidence(self):
        evidence = self.evidence()
        self.assertTrue(validate_approval_evidence(evidence))
        self.assertTrue(proposed_approval_is_current(
            evidence, now=self.now, recipient_active=True
        ))

    def test_request_has_no_approval_evidence(self):
        evidence = self.evidence(
            status=REQUESTED, approved_by_id=None, decided_at=None
        )
        self.assertTrue(validate_approval_evidence(evidence))
        self.assertFalse(proposed_approval_is_current(
            evidence, now=self.now, recipient_active=True
        ))

    def test_self_approval_denied(self):
        for actor in (self.recipient, self.requester):
            with self.subTest(actor=actor):
                self.assertFalse(validate_approval_evidence(
                    self.evidence(approved_by_id=actor)
                ))

    def test_missing_approver_denied(self):
        self.assertFalse(validate_approval_evidence(
            self.evidence(approved_by_id=None)
        ))

    def test_invalid_project_scope_denied(self):
        for projects in ((), (self.project, self.project)):
            with self.subTest(projects=projects):
                self.assertFalse(validate_approval_evidence(
                    self.evidence(project_ids=projects)
                ))

    def test_invalid_time_window_denied(self):
        self.assertFalse(validate_approval_evidence(
            self.evidence(ends_at=self.now - timedelta(days=2))
        ))

    def test_future_and_expired_windows_not_current(self):
        for changes in (
            {
                "starts_at": self.now + timedelta(days=1),
                "ends_at": self.now + timedelta(days=2),
            },
            {
                "starts_at": self.now - timedelta(days=3),
                "ends_at": self.now - timedelta(days=1),
            },
        ):
            with self.subTest(changes=changes):
                evidence = self.evidence(**changes)
                self.assertFalse(proposed_approval_is_current(
                    evidence, now=self.now, recipient_active=True
                ))

    def test_inactive_recipient_denied(self):
        self.assertFalse(proposed_approval_is_current(
            self.evidence(), now=self.now, recipient_active=False
        ))

    def test_rejected_and_expired_not_current(self):
        for state in (REJECTED, EXPIRED):
            with self.subTest(state=state):
                self.assertFalse(proposed_approval_is_current(
                    self.evidence(status=state),
                    now=self.now, recipient_active=True
                ))

    def test_revoked_evidence_not_current(self):
        evidence = self.evidence(
            status=REVOKED, revoked_at=self.now
        )
        self.assertTrue(validate_approval_evidence(evidence))
        self.assertFalse(proposed_approval_is_current(
            evidence, now=self.now, recipient_active=True
        ))

    def test_future_decision_not_current(self):
        evidence = self.evidence(
            decided_at=self.now + timedelta(minutes=1)
        )
        self.assertFalse(proposed_approval_is_current(
            evidence, now=self.now, recipient_active=True
        ))

    def test_no_operational_access(self):
        evidence = self.evidence()
        self.assertFalse(msr_approval_evidence_grants_access(evidence))