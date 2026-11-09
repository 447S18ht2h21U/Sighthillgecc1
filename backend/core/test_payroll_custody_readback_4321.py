"""Isolated tests for read-back matching and fail-closed behavior."""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .services import audit
from .payroll_audit_chain_4309 import _events
from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
)
from .payroll_custody_readback_4321 import (
    candidate_custody_readback_review,
    custody_readback_grants_live_access,
)
from .test_payroll_custody_integrated_review_4320 import (
    IntegratedCustody4320Tests,
)


class CustodyReadback4321Tests(TestCase):
    setUp = IntegratedCustody4320Tests.setUp
    assign = IntegratedCustody4320Tests.assign
    build = IntegratedCustody4320Tests.build
    receipt = IntegratedCustody4320Tests.receipt
    make_approved_msr = IntegratedCustody4320Tests.make_approved_msr
    prepare_full_payment = (
        IntegratedCustody4320Tests.prepare_full_payment
    )
    ready = IntegratedCustody4320Tests.ready
    checkpoint = IntegratedCustody4320Tests.checkpoint
    minimum = IntegratedCustody4320Tests.minimum
    registry = IntegratedCustody4320Tests.registry
    custody_receipt = IntegratedCustody4320Tests.custody_receipt
    issuer = IntegratedCustody4320Tests.issuer
    key = IntegratedCustody4320Tests.key

    custodian = "test-only-unverified-provider"

    def setup_claims(self):
        manifest = candidate_custody_manifest()
        receipt = self.custody_receipt(manifest)
        readback = {
            "custodian_id": self.custodian,
            "manifest": deepcopy(manifest),
            "receipt": deepcopy(receipt),
        }
        return receipt, readback

    def report(self, record, *, receipt=None, readback=None,
               checkpoint=None, registry=None, expected_custodian=None):
        if receipt is None or readback is None:
            default_receipt, default_readback = self.setup_claims()
            if receipt is None:
                receipt = default_receipt
            if readback is None:
                readback = default_readback

        if checkpoint is None:
            checkpoint = self.checkpoint()

        return candidate_custody_readback_review(
            payment_id=record.pk,
            checkpoint=checkpoint,
            registry=self.registry() if registry is None else registry,
            expected_issuer=self.issuer,
            trusted_minimum=self.minimum(checkpoint),
            receipt=receipt,
            readback=readback,
            expected_custodian=(
                self.custodian
                if expected_custodian is None else expected_custodian
            ),
        )

    def test_matching_readback_is_still_untrusted(self):
        record, _, _ = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertTrue(result["test_readback_fields_match"])
        self.assertFalse(result["external_custodian_authenticated"])
        self.assertFalse(result["durable_external_storage_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertFalse(result["payroll_access_authorized"])
        self.assertFalse(custody_readback_grants_live_access())

    def test_missing_readback_denied(self):
        record, _, _ = self.ready()
        receipt, _ = self.setup_claims()

        self.assertIsNone(candidate_custody_readback_review(
            payment_id=record.pk,
            checkpoint=self.checkpoint(),
            registry=self.registry(),
            expected_issuer=self.issuer,
            trusted_minimum=self.minimum(),
            receipt=receipt,
            readback=None,
            expected_custodian=self.custodian,
        ))

    def test_modified_readback_manifest_denied(self):
        record, _, _ = self.ready()
        receipt, readback = self.setup_claims()
        readback["manifest"]["audit_digest"] = "a" * 64

        self.assertIsNone(self.report(
            record, receipt=receipt, readback=readback
        ))

    def test_modified_readback_receipt_denied(self):
        record, _, _ = self.ready()
        receipt, readback = self.setup_claims()
        readback["receipt"]["acknowledged_sequence"] += 1

        self.assertIsNone(self.report(
            record, receipt=receipt, readback=readback
        ))

    def test_wrong_custodian_or_extra_claim_denied(self):
        record, _, _ = self.ready()
        receipt, readback = self.setup_claims()

        self.assertIsNone(self.report(
            record, receipt=receipt, readback=readback,
            expected_custodian="other-provider"
        ))

        forged = deepcopy(readback)
        forged["external_custodian_authenticated"] = True
        self.assertIsNone(self.report(
            record, receipt=receipt, readback=forged
        ))

    def test_stale_copy_rejected_after_new_audit_event(self):
        record, _, _ = self.ready()
        receipt, readback = self.setup_claims()
        old_checkpoint = self.checkpoint()

        audit(
            self.comptroller,
            "test.only.readback.append",
            self.project.pk,
            {"purpose": "isolated readback freshness check"},
        )

        self.assertIsNone(self.report(
            record, receipt=receipt, readback=readback,
            checkpoint=old_checkpoint
        ))

    def test_revoked_key_and_broken_chain_denied(self):
        record, _, _ = self.ready()
        self.assertIsNone(self.report(
            record, registry=self.registry(revoked=True)
        ))

        receipt, readback = self.setup_claims()
        events = _events()
        changed = deepcopy(events[0])
        changed.payload = {**changed.payload, "forged": True}
        events[0] = changed

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertIsNone(self.report(
                record, receipt=receipt, readback=readback
            ))

    def test_readback_comparison_does_not_modify_records(self):
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
        self.assertIsNotNone(self.report(record))
        self.assertEqual(before, state())
        self.assertFalse(custody_readback_grants_live_access())