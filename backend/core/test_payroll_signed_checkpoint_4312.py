"""Disposable database tests for signed checkpoint comparisons."""
import hashlib
import hmac
from copy import deepcopy

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .services import audit
from .payroll_signed_checkpoint_4312 import (
    _SCHEMA,
    _canonical_checkpoint_bytes,
    candidate_signed_checkpoint_matches,
    candidate_signed_checkpoint_payroll_evidence,
    signed_checkpoint_grants_live_access,
)
from .test_payroll_audit_checkpoint_4311 import (
    AuditCheckpoint4311Tests,
)


class SignedCheckpoint4312Tests(TestCase):
    setUp = AuditCheckpoint4311Tests.setUp
    assign = AuditCheckpoint4311Tests.assign
    build = AuditCheckpoint4311Tests.build
    receipt = AuditCheckpoint4311Tests.receipt
    make_approved_msr = AuditCheckpoint4311Tests.make_approved_msr
    prepare_full_payment = (
        AuditCheckpoint4311Tests.prepare_full_payment
    )
    ready = AuditCheckpoint4311Tests.ready

    # This fixed key is deliberately for disposable test data ONLY.
    # It is never a production secret or external trust anchor.
    key = b"VERIDIAN-ISOLATED-TEST-KEY-NOT-FOR-PRODUCTION-4312"

    def checkpoint(self):
        head = AuditHead.objects.get(pk=1)
        result = {
            "schema": _SCHEMA,
            "key_id": "disposable-test-key-4312",
            "sequence": head.sequence,
            "digest": head.digest,
        }
        result["signature"] = hmac.new(
            self.key,
            _canonical_checkpoint_bytes(result),
            hashlib.sha256,
        ).hexdigest()
        return result

    def report(self, record, checkpoint=None, key=None):
        if checkpoint is None:
            checkpoint = self.checkpoint()
        if key is None:
            key = self.key
        return candidate_signed_checkpoint_payroll_evidence(
            payment_id=record.pk,
            checkpoint=checkpoint,
            verification_key=key,
        )

    def test_matching_signature_is_candidate_only(self):
        record, _, _ = self.ready()
        result = self.report(record)
        self.assertIsNotNone(result)
        self.assertTrue(result["test_signature_matches_supplied_key"])
        self.assertFalse(result["checkpoint_source_authenticated"])
        self.assertFalse(result["external_audit_anchor_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertEqual(
            result["review_status"],
            "SIGNED_WITH_TEST_KEY_SOURCE_UNAUTHENTICATED",
        )
        self.assertFalse(signed_checkpoint_grants_live_access())

    def test_wrong_key_is_rejected(self):
        record, _, _ = self.ready()
        self.assertIsNone(self.report(
            record, key=b"ANOTHER-ISOLATED-TEST-KEY-NOT-FOR-PRODUCTION-4312"
        ))

    def test_modified_signed_digest_is_rejected(self):
        record, _, _ = self.ready()
        changed = deepcopy(self.checkpoint())
        changed["digest"] = "a" * 64
        self.assertIsNone(self.report(record, checkpoint=changed))

    def test_modified_signed_sequence_is_rejected(self):
        record, _, _ = self.ready()
        changed = deepcopy(self.checkpoint())
        changed["sequence"] += 1
        self.assertIsNone(self.report(record, checkpoint=changed))

    def test_missing_and_malformed_signature_rejected(self):
        record, _, _ = self.ready()
        original = self.checkpoint()

        for change in (
            {"signature": None},
            {"signature": "not-a-signature"},
            {"schema": "UNRECOGNIZED"},
            {"key_id": "changed-key-id"},
            {"sequence": True},
        ):
            with self.subTest(change=change):
                altered = {**original, **change}
                self.assertIsNone(
                    self.report(record, checkpoint=altered)
                )

        incomplete = dict(original)
        del incomplete["signature"]
        self.assertIsNone(self.report(
            record, checkpoint=incomplete
        ))
        self.assertFalse(candidate_signed_checkpoint_matches(
            checkpoint=original, verification_key=b"short"
        ))

    def test_old_signed_checkpoint_survives_valid_append(self):
        record, _, _ = self.ready()
        saved = self.checkpoint()

        audit(
            self.comptroller,
            "test.only.signed.checkpoint.append",
            self.project.pk,
            {"purpose": "disposable append-only validation"},
        )

        result = self.report(record, checkpoint=saved)
        self.assertIsNotNone(result)
        self.assertEqual(
            result["checkpoint_sequence"], saved["sequence"]
        )

    def test_valid_signature_cannot_bypass_missing_payment(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_signed_comparison_preserves_database(self):
        record, _, _ = self.ready()
        checkpoint = self.checkpoint()

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
        self.assertIsNotNone(
            self.report(record, checkpoint=checkpoint)
        )
        self.assertEqual(before, state())
        self.assertFalse(signed_checkpoint_grants_live_access())