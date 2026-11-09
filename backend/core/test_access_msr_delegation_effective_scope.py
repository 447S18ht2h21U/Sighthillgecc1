import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.access_msr_delegation_effective_scope import (
    EffectiveScopeEvidence,
    evaluate_fixed_msr_scope,
    effective_scope_grants_live_msr_access,
)


class EffectiveScopeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        self.request = uuid4()
        self.recipient = uuid4()
        self.project = uuid4()
        self.source = uuid4()
        self.evidence = EffectiveScopeEvidence(
            request_id=self.request,
            recipient_id=self.recipient,
            project_id=self.project,
            original_owner_id=self.source,
            captured_revision=0,
            decision_request_id=self.request,
            decision_result="APPROVED",
            begins_at=self.now - timedelta(hours=1),
            ends_at=self.now + timedelta(hours=1),
            terminated=False,
            project_invalidated=False,
        )

    def valid(self, evidence=None, **changes):
        args = dict(
            recipient_id=self.recipient,
            project_id=self.project,
            current_owner_id=self.source,
            current_revision=0,
            now=self.now,
            recipient_active=True,
        )
        args.update(changes)
        return evaluate_fixed_msr_scope(
            self.evidence if evidence is None else evidence, **args
        )

    def test_approved_exact_scope(self):
        self.assertTrue(self.valid())

    def test_wrong_recipient(self):
        self.assertFalse(self.valid(recipient_id=uuid4()))

    def test_wrong_project(self):
        self.assertFalse(self.valid(project_id=uuid4()))

    def test_reassigned_owner(self):
        self.assertFalse(self.valid(current_owner_id=uuid4()))

    def test_reassigned_then_returned(self):
        self.assertFalse(self.valid(current_revision=2))

    def test_stale_revision(self):
        self.assertFalse(self.valid(current_revision=1))

    def test_rejected_decision(self):
        self.assertFalse(self.valid(replace(
            self.evidence, decision_result="REJECTED"
        )))

    def test_mismatched_decision_request(self):
        self.assertFalse(self.valid(replace(
            self.evidence, decision_request_id=uuid4()
        )))

    def test_terminated(self):
        self.assertFalse(self.valid(replace(
            self.evidence, terminated=True
        )))

    def test_invalidation(self):
        self.assertFalse(self.valid(replace(
            self.evidence, project_invalidated=True
        )))

    def test_inactive_recipient(self):
        self.assertFalse(self.valid(recipient_active=False))

    def test_before_start(self):
        self.assertFalse(self.valid(now=self.evidence.begins_at -
                                    timedelta(microseconds=1)))

    def test_exact_start_allowed(self):
        self.assertTrue(self.valid(now=self.evidence.begins_at))

    def test_exact_expiration_denied(self):
        self.assertFalse(self.valid(now=self.evidence.ends_at))

    def test_invalid_time_window(self):
        self.assertFalse(self.valid(replace(
            self.evidence, begins_at=self.evidence.ends_at
        )))

    def test_naive_datetime_denied(self):
        self.assertFalse(self.valid(now=datetime(2026, 10, 31, 12)))

    def test_untrusted_evidence_denied(self):
        self.assertFalse(self.valid(evidence={"approved": True}))

    def test_boolean_revision_denied(self):
        self.assertFalse(self.valid(current_revision=True))

    def test_invalid_boolean_evidence_denied(self):
        self.assertFalse(self.valid(replace(
            self.evidence, terminated=0
        )))

    def test_no_operational_access(self):
        self.assertFalse(effective_scope_grants_live_msr_access())


if __name__ == "__main__":
    unittest.main()