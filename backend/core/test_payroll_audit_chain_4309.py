"""Isolated original audit-chain recomputation and tamper tests."""
from copy import copy
from unittest.mock import patch

from django.test import TestCase

from .models import AuditHead, Outbox
from .payroll_audit_chain_4309 import (
    _events,
    _outboxes,
    candidate_complete_audit_chain,
    audit_chain_candidate_grants_live_access,
)
from .test_payroll_payment_technical_link_4300 import (
    PaymentTechnicalLink4300Tests,
)


class AuditChain4309Tests(TestCase):
    setUp = PaymentTechnicalLink4300Tests.setUp
    assign = PaymentTechnicalLink4300Tests.assign
    build = PaymentTechnicalLink4300Tests.build

    def ready(self):
        self.assign()
        return self.build()

    def test_real_original_audit_events_verify(self):
        self.ready()
        self.assertTrue(candidate_complete_audit_chain())
        self.assertFalse(audit_chain_candidate_grants_live_access())

    def test_modified_event_payload_is_rejected(self):
        self.ready()
        events = _events()
        altered = copy(events[0])
        altered.payload = {
            **events[0].payload, "tampered": "yes"
        }
        events[0] = altered

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertFalse(candidate_complete_audit_chain())

    def test_modified_digest_is_rejected(self):
        self.ready()
        events = _events()
        altered = copy(events[0])
        altered.digest = "f" * 64
        events[0] = altered

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertFalse(candidate_complete_audit_chain())

    def test_broken_previous_hash_is_rejected(self):
        self.ready()
        events = _events()
        altered = copy(events[-1])
        altered.previous_hash = "a" * 64
        events[-1] = altered

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertFalse(candidate_complete_audit_chain())

    def test_missing_middle_event_is_rejected(self):
        self.ready()
        events = _events()
        self.assertGreaterEqual(len(events), 3)
        incomplete = events[:1] + events[2:]

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=incomplete,
        ):
            self.assertFalse(candidate_complete_audit_chain())

    def test_changed_audit_head_is_rejected(self):
        self.ready()
        original = AuditHead.objects.get(pk=1)
        altered = copy(original)
        altered.digest = "b" * 64

        with patch(
            "core.payroll_audit_chain_4309._head",
            return_value=[altered],
        ):
            self.assertFalse(candidate_complete_audit_chain())

    def test_missing_or_altered_outbox_is_rejected(self):
        self.ready()
        outboxes = _outboxes()

        with patch(
            "core.payroll_audit_chain_4309._outboxes",
            return_value=outboxes[:-1],
        ):
            self.assertFalse(candidate_complete_audit_chain())

        altered = copy(outboxes[0])
        altered.topic = "INCORRECT_TOPIC"
        changed = [altered] + outboxes[1:]

        with patch(
            "core.payroll_audit_chain_4309._outboxes",
            return_value=changed,
        ):
            self.assertFalse(candidate_complete_audit_chain())

    def test_verification_does_not_modify_records(self):
        self.ready()

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                [
                    (e.pk, e.sequence, e.previous_hash, e.digest)
                    for e in _events()
                ],
                [
                    (o.pk, o.event_id, o.topic)
                    for o in _outboxes()
                ],
            )

        before = state()
        self.assertTrue(candidate_complete_audit_chain())
        self.assertEqual(before, state())
        self.assertFalse(audit_chain_candidate_grants_live_access())