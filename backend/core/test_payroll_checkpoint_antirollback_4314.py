"""Database-backed anti-rollback tests with disposable trust fixtures."""
from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .services import audit
from .payroll_checkpoint_antirollback_4314 import (
    candidate_antirollback_payroll_evidence,
    antirollback_candidate_grants_live_access,
)
from .test_payroll_checkpoint_key_custody_4313 import (
    CheckpointKeyCustody4313Tests,
)


class CheckpointAntiRollback4314Tests(TestCase):
    setUp = CheckpointKeyCustody4313Tests.setUp
    assign = CheckpointKeyCustody4313Tests.assign
    build = CheckpointKeyCustody4313Tests.build
    receipt = CheckpointKeyCustody4313Tests.receipt
    make_approved_msr = CheckpointKeyCustody4313Tests.make_approved_msr
    prepare_full_payment = (
        CheckpointKeyCustody4313Tests.prepare_full_payment
    )
    ready = CheckpointKeyCustody4313Tests.ready
    checkpoint = CheckpointKeyCustody4313Tests.checkpoint
    registry = CheckpointKeyCustody4313Tests.registry
    key = CheckpointKeyCustody4313Tests.key
    issuer = CheckpointKeyCustody4313Tests.issuer

    def minimum(self, checkpoint=None):
        if checkpoint is None:
            checkpoint = self.checkpoint()
        return {
            "issuer_id": self.issuer,
            "key_id": checkpoint["key_id"],
            "minimum_sequence": checkpoint["sequence"],
            "minimum_digest": checkpoint["digest"],
        }

    def report(self, record, *, checkpoint=None, minimum=None,
               registry=None, expected_issuer=None):
        if checkpoint is None:
            checkpoint = self.checkpoint()
        if minimum is None:
            minimum = self.minimum(checkpoint)
        if registry is None:
            registry = self.registry()
        if expected_issuer is None:
            expected_issuer = self.issuer

        return candidate_antirollback_payroll_evidence(
            payment_id=record.pk,
            checkpoint=checkpoint,
            registry=registry,
            expected_issuer=expected_issuer,
            trusted_minimum=minimum,
        )

    def append_event(self):
        audit(
            self.comptroller,
            "test.only.antirollback.append",
            self.project.pk,
            {"purpose": "disposable anti-rollback validation"},
        )

    def test_matching_floor_is_candidate_only(self):
        record, _, _ = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertTrue(result["test_minimum_reference_matched"])
        self.assertFalse(result["minimum_reference_source_authenticated"])
        self.assertFalse(result["external_audit_anchor_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertFalse(antirollback_candidate_grants_live_access())

    def test_older_signed_checkpoint_rejected_after_new_floor(self):
        record, _, _ = self.ready()
        older = self.checkpoint()
        self.append_event()
        newest = self.checkpoint()

        self.assertIsNone(self.report(
            record,
            checkpoint=older,
            minimum=self.minimum(newest),
        ))
        self.assertIsNotNone(self.report(
            record,
            checkpoint=newest,
            minimum=self.minimum(newest),
        ))

    def test_newer_signed_checkpoint_accepted_against_old_floor(self):
        record, _, _ = self.ready()
        previous = self.checkpoint()
        self.append_event()
        newer = self.checkpoint()

        result = self.report(
            record,
            checkpoint=newer,
            minimum=self.minimum(previous),
        )
        self.assertIsNotNone(result)
        self.assertEqual(
            result["minimum_sequence_checked"],
            previous["sequence"],
        )

    def test_wrong_trusted_digest_rejected(self):
        record, _, _ = self.ready()
        floor = self.minimum()
        floor["minimum_digest"] = "f" * 64

        self.assertIsNone(self.report(record, minimum=floor))

    def test_wrong_issuer_and_key_binding_rejected(self):
        record, _, _ = self.ready()
        floor = self.minimum()
        floor["issuer_id"] = "wrong-test-issuer"
        self.assertIsNone(self.report(record, minimum=floor))

        floor = self.minimum()
        floor["key_id"] = "wrong-test-key"
        self.assertIsNone(self.report(record, minimum=floor))

    def test_invalid_minimum_records_rejected(self):
        record, _, _ = self.ready()

        for floor in (
            None,
            {},
            {"invalid": True},
            {**self.minimum(), "minimum_sequence": True},
            {**self.minimum(), "minimum_sequence": 0},
            {**self.minimum(), "minimum_digest": "invalid"},
            {**self.minimum(), "minimum_sequence": 999999},
        ):
            with self.subTest(floor=floor):
                self.assertIsNone(
                    candidate_antirollback_payroll_evidence(
                        payment_id=record.pk,
                        checkpoint=self.checkpoint(),
                        registry=self.registry(),
                        expected_issuer=self.issuer,
                        trusted_minimum=floor,
                    )
                )

    def test_signature_and_customer_payment_gates_remain_required(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.report(record))

        bad_registry = self.registry(revoked=True)
        self.assertIsNone(
            self.report(record, registry=bad_registry)
        )

    def test_candidate_read_never_mutates_database(self):
        record, _, _ = self.ready()

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                list(AuditEvent.objects.order_by("sequence").values_list(
                    "pk", "sequence", "digest"
                )),
                list(Outbox.objects.order_by("pk").values_list(
                    "pk", "event_id", "topic"
                )),
            )

        before = state()
        self.assertIsNotNone(self.report(record))
        self.assertEqual(before, state())
        self.assertFalse(antirollback_candidate_grants_live_access())