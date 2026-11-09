"""Isolated tests for immutable MSR delegation evidence design."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_msr_delegation_immutable_evidence import (
    MSRDelegationRequestEvidence,
    MSRDelegationDecisionEvidence,
    MSRDelegationTerminationEvidence,
    valid_request_evidence,
    valid_decision_evidence,
    valid_termination_evidence,
    proposed_delegation_is_current,
    immutable_evidence_grants_access,
)


class ImmutableMSRDelegationEvidenceTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.source = uuid4()
        self.approver = uuid4()
        self.request = MSRDelegationRequestEvidence(
            request_id=uuid4(),
            recipient_id=self.recipient,
            requested_by_id=self.requester,
            source_associate_id=self.source,
            project_ids=(uuid4(),),
            requested_at=self.now - timedelta(hours=2),
            starts_at=self.now - timedelta(hours=1),
            ends_at=self.now + timedelta(days=1),
            reason="Temporary vacation project coverage.",
        )
        self.decision = MSRDelegationDecisionEvidence(
            decision_id=uuid4(),
            request_id=self.request.request_id,
            decided_by_id=self.approver,
            decision="APPROVED",
            decided_at=self.now - timedelta(minutes=30),
            reason="Independent coverage approval.",
            authority_reference="verified-manager-authorization",
        )

    def termination(self, kind="ADMINISTRATIVE_REVOCATION", **changes):
        values = {
            "termination_id": uuid4(),
            "decision_id": self.decision.decision_id,
            "terminated_by_id": uuid4(),
            "termination_kind": kind,
            "terminated_at": self.now,
            "reason": "Coverage is no longer required.",
            "authority_reference": "verified-revocation-authority",
        }
        values.update(changes)
        return MSRDelegationTerminationEvidence(**values)

    def test_request_and_decision_are_valid(self):
        self.assertTrue(valid_request_evidence(self.request))
        self.assertTrue(valid_decision_evidence(self.request, self.decision))

    def test_approval_is_proposed_current(self):
        self.assertTrue(proposed_delegation_is_current(
            self.request, self.decision,
            now=self.now, recipient_active=True
        ))

    def test_request_and_decision_mismatch_denied(self):
        changed = replace(self.decision, request_id=uuid4())
        self.assertFalse(valid_decision_evidence(self.request, changed))

    def test_decision_before_request_denied(self):
        changed = replace(
            self.decision,
            decided_at=self.request.requested_at - timedelta(seconds=1),
        )
        self.assertFalse(valid_decision_evidence(self.request, changed))

    def test_self_approval_denied(self):
        for actor in (self.recipient, self.requester):
            with self.subTest(actor=actor):
                changed = replace(self.decision, decided_by_id=actor)
                self.assertFalse(valid_decision_evidence(
                    self.request, changed
                ))

    def test_rejected_decision_is_not_current(self):
        changed = replace(self.decision, decision="REJECTED")
        self.assertFalse(proposed_delegation_is_current(
            self.request, changed, now=self.now, recipient_active=True
        ))

    def test_inactive_recipient_denied(self):
        self.assertFalse(proposed_delegation_is_current(
            self.request, self.decision,
            now=self.now, recipient_active=False
        ))

    def test_future_and_expired_windows_denied(self):
        future = replace(
            self.request,
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=2),
        )
        expired = replace(
            self.request,
            ends_at=self.now - timedelta(minutes=1),
        )
        for request in (future, expired):
            with self.subTest(request=request):
                self.assertFalse(proposed_delegation_is_current(
                    request, self.decision,
                    now=self.now, recipient_active=True
                ))

    def test_revocation_ends_proposed_eligibility(self):
        termination = self.termination()
        self.assertTrue(valid_termination_evidence(
            self.request, self.decision, termination
        ))
        self.assertFalse(proposed_delegation_is_current(
            self.request, self.decision,
            now=self.now, recipient_active=True,
            termination=termination,
        ))

    def test_surrender_must_match_recipient(self):
        valid = self.termination(
            kind="VOLUNTARY_SURRENDER",
            terminated_by_id=self.recipient,
        )
        invalid = self.termination(
            kind="VOLUNTARY_SURRENDER",
            terminated_by_id=self.approver,
        )
        self.assertTrue(valid_termination_evidence(
            self.request, self.decision, valid
        ))
        self.assertFalse(valid_termination_evidence(
            self.request, self.decision, invalid
        ))

    def test_automatic_expiration_does_not_require_actor(self):
        termination = self.termination(
            kind="AUTOMATIC_EXPIRATION",
            terminated_by_id=None,
            terminated_at=self.request.ends_at,
        )
        self.assertTrue(valid_termination_evidence(
            self.request, self.decision, termination
        ))

    def test_evidence_never_grants_operational_access(self):
        self.assertFalse(immutable_evidence_grants_access(
            self.request, self.decision
        ))