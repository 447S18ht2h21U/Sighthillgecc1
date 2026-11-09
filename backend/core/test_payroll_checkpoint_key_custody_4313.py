"""Disposable database signing-key custody boundary regression."""
from copy import deepcopy
import hashlib
import hmac

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .payroll_signed_checkpoint_4312 import (
    _canonical_checkpoint_bytes,
    candidate_signed_checkpoint_matches,
)
from .payroll_checkpoint_key_custody_4313 import (
    _PURPOSE,
    candidate_registered_checkpoint_evidence,
    custody_candidate_grants_live_access,
)
from .test_payroll_signed_checkpoint_4312 import (
    SignedCheckpoint4312Tests,
)


class CheckpointKeyCustody4313Tests(TestCase):
    setUp = SignedCheckpoint4312Tests.setUp
    assign = SignedCheckpoint4312Tests.assign
    build = SignedCheckpoint4312Tests.build
    receipt = SignedCheckpoint4312Tests.receipt
    make_approved_msr = SignedCheckpoint4312Tests.make_approved_msr
    prepare_full_payment = (
        SignedCheckpoint4312Tests.prepare_full_payment
    )
    ready = SignedCheckpoint4312Tests.ready
    checkpoint = SignedCheckpoint4312Tests.checkpoint
    key = SignedCheckpoint4312Tests.key

    issuer = "independent-custodian-test-fixture"

    def registry(self, **changes):
        entry = {
            "key_id": "disposable-test-key-4312",
            "issuer_id": self.issuer,
            "purpose": _PURPOSE,
            "verification_key": self.key,
            "revoked": False,
            "first_sequence": 1,
            "last_sequence": None,
        }
        entry.update(changes)
        return {entry["key_id"]: entry}

    def report(self, record, checkpoint=None, registry=None,
               expected_issuer=None):
        return candidate_registered_checkpoint_evidence(
            payment_id=record.pk,
            checkpoint=self.checkpoint() if checkpoint is None else checkpoint,
            registry=self.registry() if registry is None else registry,
            expected_issuer=(
                self.issuer if expected_issuer is None else expected_issuer
            ),
        )

    def test_matching_test_registry_remains_unauthenticated(self):
        record, _, _ = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertTrue(result["test_registry_key_matched"])
        self.assertFalse(result["registry_source_authenticated"])
        self.assertFalse(result["external_audit_anchor_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertEqual(
            result["review_status"],
            "TEST_REGISTRY_MATCHED_NO_INDEPENDENT_CUSTODY",
        )
        self.assertFalse(custody_candidate_grants_live_access())

    def test_unknown_key_id_denied(self):
        record, _, _ = self.ready()
        altered = dict(self.checkpoint())
        altered["key_id"] = "unregistered-key"
        self.assertIsNone(self.report(record, checkpoint=altered))

    def test_revoked_key_denied(self):
        record, _, _ = self.ready()
        self.assertIsNone(self.report(
            record, registry=self.registry(revoked=True)
        ))

    def test_wrong_issuer_or_purpose_denied(self):
        record, _, _ = self.ready()

        self.assertIsNone(self.report(
            record, expected_issuer="other-custodian"
        ))
        self.assertIsNone(self.report(
            record, registry=self.registry(purpose="PAYROLL_APPROVAL")
        ))

    def test_key_substitution_denied_despite_valid_signature(self):
        record, _, _ = self.ready()
        forged_key = b"DIFFERENT-DISPOSABLE-TEST-KEY-4313-NOT-PRODUCTION"
        forged = dict(self.checkpoint())
        forged["signature"] = hmac.new(
            forged_key,
            _canonical_checkpoint_bytes(forged),
            hashlib.sha256,
        ).hexdigest()

        self.assertTrue(candidate_signed_checkpoint_matches(
            checkpoint=forged,
            verification_key=forged_key,
        ))
        self.assertIsNone(self.report(record, checkpoint=forged))

    def test_sequence_range_and_invalid_registry_denied(self):
        record, _, _ = self.ready()
        sequence = self.checkpoint()["sequence"]

        for registry in (
            self.registry(first_sequence=sequence + 1),
            self.registry(last_sequence=sequence - 1),
            self.registry(first_sequence=True),
            self.registry(verification_key=b"short"),
            {},
        ):
            with self.subTest(registry=str(registry.keys())):
                self.assertIsNone(self.report(
                    record, registry=registry
                ))

    def test_valid_key_cannot_bypass_missing_full_payment(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_registry_comparison_does_not_modify_database(self):
        record, _, _ = self.ready()

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                list(AuditEvent.objects.values_list(
                    "pk", "sequence", "digest"
                )),
                list(Outbox.objects.values_list(
                    "pk", "event_id", "topic"
                )),
            )

        before = state()
        result = self.report(record)
        self.assertIsNotNone(result)
        self.assertEqual(state(), before)
        self.assertFalse(custody_candidate_grants_live_access())