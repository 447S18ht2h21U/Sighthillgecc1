"""Security tests for proposed permission authorization evidence."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_user_permission_evidence_design import (
    PermissionRequestEvidence,
    PermissionDecisionEvidence,
    PermissionTerminationEvidence,
    valid_request_evidence,
    valid_decision_evidence,
    valid_termination_evidence,
    permission_evidence_activates_access,
)


class UserPermissionEvidenceDesignTests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.recipient = uuid4()
        self.requester = uuid4()
        self.approver = uuid4()
        self.admin = uuid4()

        self.request = PermissionRequestEvidence(
            request_id=uuid4(),
            recipient_id=self.recipient,
            requested_by_id=self.requester,
            permission_code="compensation.own.view",
            reason="Employee requires personal compensation access.",
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
            reason="Independent approval documented.",
        )

    def termination(self, kind, actor, at=None):
        return PermissionTerminationEvidence(
            request_id=self.request.request_id,
            termination_id=uuid4(),
            terminated_by_id=actor,
            termination_kind=kind,
            terminated_at=at or self.now + timedelta(days=2),
            reason="Documented termination.",
        )

    def test_valid_request_evidence(self):
        self.assertTrue(valid_request_evidence(self.request))

    def test_unknown_permission_rejected(self):
        self.assertFalse(valid_request_evidence(replace(
            self.request, permission_code="permission.not.registered"
        )))

    def test_missing_identity_and_reason_rejected(self):
        self.assertFalse(valid_request_evidence(replace(
            self.request, recipient_id=None
        )))
        self.assertFalse(valid_request_evidence(replace(
            self.request, reason=" "
        )))

    def test_invalid_request_time_window_rejected(self):
        self.assertFalse(valid_request_evidence(replace(
            self.request, ends_at=self.request.starts_at
        )))
        self.assertFalse(valid_request_evidence(replace(
            self.request, starts_at=datetime(2026, 10, 26, 12)
        )))

    def test_valid_independent_approval(self):
        self.assertTrue(valid_decision_evidence(
            self.request, self.decision
        ))

    def test_self_approval_and_requester_approval_rejected(self):
        for actor in (self.recipient, self.requester):
            with self.subTest(actor=actor):
                self.assertFalse(valid_decision_evidence(
                    self.request,
                    replace(self.decision, decided_by_id=actor),
                ))

    def test_wrong_request_and_early_decision_rejected(self):
        self.assertFalse(valid_decision_evidence(
            self.request,
            replace(self.decision, request_id=uuid4()),
        ))
        self.assertFalse(valid_decision_evidence(
            self.request,
            replace(
                self.decision,
                decided_at=self.now - timedelta(seconds=1),
            ),
        ))

    def test_valid_voluntary_surrender(self):
        self.assertTrue(valid_termination_evidence(
            self.request,
            self.decision,
            self.termination("VOLUNTARY_SURRENDER", self.recipient),
        ))

    def test_other_person_cannot_surrender(self):
        self.assertFalse(valid_termination_evidence(
            self.request,
            self.decision,
            self.termination("VOLUNTARY_SURRENDER", self.admin),
        ))

    def test_administrative_revocation_evidence(self):
        self.assertTrue(valid_termination_evidence(
            self.request,
            self.decision,
            self.termination("ADMINISTRATIVE_REVOCATION", self.admin),
        ))
        for actor in (self.recipient, self.requester):
            with self.subTest(actor=actor):
                self.assertFalse(valid_termination_evidence(
                    self.request,
                    self.decision,
                    self.termination("ADMINISTRATIVE_REVOCATION", actor),
                ))

    def test_expiration_requires_end_of_period(self):
        self.assertTrue(valid_termination_evidence(
            self.request,
            self.decision,
            self.termination(
                "AUTOMATIC_EXPIRATION",
                None,
                self.request.ends_at,
            ),
        ))
        self.assertFalse(valid_termination_evidence(
            self.request,
            self.decision,
            self.termination(
                "AUTOMATIC_EXPIRATION",
                None,
                self.request.ends_at - timedelta(seconds=1),
            ),
        ))

    def test_invalid_termination_identity_or_decision_rejected(self):
        termination = self.termination(
            "ADMINISTRATIVE_REVOCATION", self.admin
        )
        self.assertFalse(valid_termination_evidence(
            self.request,
            self.decision,
            replace(termination, request_id=uuid4()),
        ))
        self.assertFalse(valid_termination_evidence(
            self.request,
            replace(self.decision, decision="REJECTED"),
            termination,
        ))

    def test_evidence_dataclasses_are_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            self.request.permission_code = "compensation.all.view"
        with self.assertRaises(FrozenInstanceError):
            self.decision.decision = "REJECTED"

    def test_evidence_never_activates_access(self):
        self.assertTrue(valid_request_evidence(self.request))
        self.assertTrue(valid_decision_evidence(
            self.request, self.decision
        ))
        self.assertFalse(permission_evidence_activates_access(
            self.request, self.decision
        ))