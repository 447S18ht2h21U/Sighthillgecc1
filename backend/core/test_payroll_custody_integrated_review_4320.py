"""Isolated integrated custody and payroll-evidence regression."""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .services import audit
from .payroll_audit_chain_4309 import _events
from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
)
from .payroll_custody_integrated_review_4320 import (
    candidate_integrated_custody_review,
    integrated_custody_grants_live_access,
)
from .test_payroll_checkpoint_antirollback_4314 import (
    CheckpointAntiRollback4314Tests,
)


class IntegratedCustody4320Tests(TestCase):
    setUp = CheckpointAntiRollback4314Tests.setUp
    assign = CheckpointAntiRollback4314Tests.assign
    build = CheckpointAntiRollback4314Tests.build
    receipt = CheckpointAntiRollback4314Tests.receipt
    make_approved_msr = (
        CheckpointAntiRollback4314Tests.make_approved_msr
    )
    prepare_full_payment = (
        CheckpointAntiRollback4314Tests.prepare_full_payment
    )
    ready = CheckpointAntiRollback4314Tests.ready
    checkpoint = CheckpointAntiRollback4314Tests.checkpoint
    minimum = CheckpointAntiRollback4314Tests.minimum
    registry = CheckpointAntiRollback4314Tests.registry
    issuer = CheckpointAntiRollback4314Tests.issuer
    key = CheckpointAntiRollback4314Tests.key

    def custody_receipt(self, manifest):
        return {
            "manifest_sha256": manifest["manifest_sha256"],
            "custodian_id": "test-only-unverified-provider",
            "acknowledged_sequence": manifest["audit_sequence"],
        }

    def report(self, record, *, checkpoint=None, registry=None,
               minimum=None, receipt=None):
        if checkpoint is None:
            checkpoint = self.checkpoint()
        if registry is None:
            registry = self.registry()
        if minimum is None:
            minimum = self.minimum(checkpoint)
        if receipt is None:
            receipt = self.custody_receipt(
                candidate_custody_manifest()
            )

        return candidate_integrated_custody_review(
            payment_id=record.pk,
            checkpoint=checkpoint,
            registry=registry,
            expected_issuer=self.issuer,
            trusted_minimum=minimum,
            receipt=receipt,
        )

    def test_complete_evidence_stays_untrusted_and_unapproved(self):
        record, _, _ = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertTrue(result["custody_receipt_fields_match"])
        self.assertFalse(result["external_custodian_authenticated"])
        self.assertFalse(result["durable_external_storage_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertFalse(result["payroll_access_authorized"])
        self.assertFalse(integrated_custody_grants_live_access())

    def test_changed_custody_receipt_denied(self):
        record, _, _ = self.ready()
        manifest = candidate_custody_manifest()
        receipt = self.custody_receipt(manifest)
        receipt["manifest_sha256"] = "f" * 64
        self.assertIsNone(self.report(record, receipt=receipt))

    def test_forged_receipt_authentication_claim_denied(self):
        record, _, _ = self.ready()
        manifest = candidate_custody_manifest()
        receipt = self.custody_receipt(manifest)
        receipt["external_custodian_authenticated"] = True
        self.assertIsNone(self.report(record, receipt=receipt))

    def test_revoked_signing_key_denied(self):
        record, _, _ = self.ready()
        self.assertIsNone(self.report(
            record, registry=self.registry(revoked=True)
        ))

    def test_invalid_trusted_minimum_denied(self):
        record, _, _ = self.ready()
        minimum = self.minimum()
        minimum["minimum_digest"] = "a" * 64
        self.assertIsNone(self.report(
            record, minimum=minimum
        ))

    def test_older_checkpoint_denied_after_valid_append(self):
        record, _, _ = self.ready()
        old = self.checkpoint()

        audit(
            self.comptroller,
            "test.only.integrated.custody.append",
            self.project.pk,
            {"purpose": "isolated current-head binding check"},
        )

        manifest = candidate_custody_manifest()
        receipt = self.custody_receipt(manifest)

        self.assertIsNone(self.report(
            record,
            checkpoint=old,
            minimum=self.minimum(old),
            receipt=receipt,
        ))

    def test_tampered_chain_prevents_integrated_review(self):
        record, _, _ = self.ready()
        original_receipt = self.custody_receipt(
            candidate_custody_manifest()
        )
        events = _events()
        changed = deepcopy(events[0])
        changed.payload = {**changed.payload, "forged": True}
        events[0] = changed

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertIsNone(self.report(
                record, receipt=original_receipt
            ))

    def test_integrated_read_has_no_database_side_effects(self):
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
        self.assertFalse(integrated_custody_grants_live_access())