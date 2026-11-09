"""Database-backed tests for external-reference audit comparisons."""
from copy import copy
from unittest.mock import patch

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .services import audit
from .payroll_audit_chain_4309 import _events
from .payroll_audit_checkpoint_4311 import (
    candidate_checkpoint_matches,
    candidate_checkpoint_checked_payroll_evidence,
    checkpoint_comparison_grants_live_access,
)
from .test_payroll_audit_verified_lineage_4310 import (
    AuditVerifiedLineage4310Tests,
)


class AuditCheckpoint4311Tests(TestCase):
    setUp = AuditVerifiedLineage4310Tests.setUp
    assign = AuditVerifiedLineage4310Tests.assign
    build = AuditVerifiedLineage4310Tests.build
    receipt = AuditVerifiedLineage4310Tests.receipt
    make_approved_msr = (
        AuditVerifiedLineage4310Tests.make_approved_msr
    )
    prepare_full_payment = (
        AuditVerifiedLineage4310Tests.prepare_full_payment
    )
    ready = AuditVerifiedLineage4310Tests.ready

    def anchor(self):
        head = AuditHead.objects.get(pk=1)
        return head.sequence, head.digest

    def report(self, record, sequence, digest):
        return candidate_checkpoint_checked_payroll_evidence(
            payment_id=record.pk,
            anchor_sequence=sequence,
            anchor_digest=digest,
        )

    def test_matching_checkpoint_returns_untrusted_candidate_only(self):
        record, _, _ = self.ready()
        sequence, digest = self.anchor()

        result = self.report(record, sequence, digest)

        self.assertIsNotNone(result)
        self.assertTrue(result["checkpoint_comparison_passed"])
        self.assertFalse(result["checkpoint_source_authenticated"])
        self.assertFalse(result["external_audit_anchor_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertEqual(
            result["review_status"],
            "CHECKPOINT_MATCHED_SOURCE_UNAUTHENTICATED_TEST_ONLY",
        )
        self.assertFalse(checkpoint_comparison_grants_live_access())

    def test_wrong_digest_denied(self):
        record, _, _ = self.ready()
        sequence, digest = self.anchor()
        changed = ("0" if digest[0] != "0" else "1") + digest[1:]
        self.assertIsNone(self.report(record, sequence, changed))

    def test_missing_and_malformed_checkpoint_denied(self):
        record, _, _ = self.ready()
        sequence, digest = self.anchor()

        for bad_sequence, bad_digest in (
            (None, digest),
            (True, digest),
            (0, digest),
            (sequence + 100, digest),
            (sequence, None),
            (sequence, "invalid"),
            (sequence, digest.upper() + "x"),
        ):
            with self.subTest(
                sequence=bad_sequence, digest=bad_digest
            ):
                self.assertIsNone(
                    self.report(record, bad_sequence, bad_digest)
                )

    def test_earlier_checkpoint_survives_valid_new_audit_event(self):
        record, _, _ = self.ready()
        sequence, digest = self.anchor()

        audit(
            self.comptroller,
            "test.only.checkpoint.append",
            self.project.pk,
            {"purpose": "isolated append-only checkpoint test"},
        )

        head = AuditHead.objects.get(pk=1)
        self.assertEqual(head.sequence, sequence + 1)
        self.assertTrue(candidate_checkpoint_matches(
            anchor_sequence=sequence,
            anchor_digest=digest,
        ))
        self.assertIsNotNone(self.report(record, sequence, digest))

    def test_historical_checkpoint_mismatch_denied(self):
        record, _, _ = self.ready()
        events = _events()
        self.assertGreaterEqual(len(events), 2)

        old = events[0]
        newer = events[-1]

        self.assertFalse(candidate_checkpoint_matches(
            anchor_sequence=old.sequence,
            anchor_digest=newer.digest,
        ))
        self.assertIsNone(
            self.report(record, old.sequence, newer.digest)
        )

    def test_tampered_audit_chain_denied_despite_matching_reference(self):
        record, _, _ = self.ready()
        sequence, digest = self.anchor()
        events = _events()
        altered = copy(events[0])
        altered.payload = {**altered.payload, "tampered": True}
        events[0] = altered

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertIsNone(self.report(record, sequence, digest))

    def test_incomplete_payment_stays_denied_with_valid_checkpoint(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        sequence, digest = self.anchor()

        self.assertIsNone(self.report(record, sequence, digest))

    def test_checkpoint_comparison_is_read_only(self):
        record, _, _ = self.ready()
        sequence, digest = self.anchor()

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                list(AuditEvent.objects.order_by("sequence").values_list(
                    "pk", "sequence", "previous_hash", "digest"
                )),
                list(Outbox.objects.order_by("pk").values_list(
                    "pk", "event_id", "topic"
                )),
            )

        before = state()
        self.assertIsNotNone(self.report(record, sequence, digest))
        self.assertEqual(before, state())
        self.assertFalse(checkpoint_comparison_grants_live_access())