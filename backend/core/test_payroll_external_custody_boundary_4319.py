"""Disposable database tests for the provider-neutral custody boundary."""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .payroll_audit_chain_4309 import _events
from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
    candidate_custody_receipt_comparison,
    external_custody_boundary_grants_live_access,
)
from .test_payroll_payment_technical_link_4300 import (
    PaymentTechnicalLink4300Tests,
)


class ExternalCustodyBoundary4319Tests(TestCase):
    setUp = PaymentTechnicalLink4300Tests.setUp
    assign = PaymentTechnicalLink4300Tests.assign
    build = PaymentTechnicalLink4300Tests.build

    def ready(self):
        self.assign()
        return self.build()

    def receipt(self, manifest):
        return {
            "manifest_sha256": manifest["manifest_sha256"],
            "custodian_id": "disposable-test-custodian",
            "acknowledged_sequence": manifest["audit_sequence"],
        }

    def test_manifest_uses_verified_current_audit_head(self):
        self.ready()
        manifest = candidate_custody_manifest()
        head = AuditHead.objects.get(pk=1)
        self.assertIsNotNone(manifest)
        self.assertEqual(
            manifest["audit_sequence"], head.sequence
        )
        self.assertEqual(
            manifest["audit_digest"], head.digest
        )
        self.assertEqual(
            manifest["environment"], "ISOLATED_TEST"
        )

    def test_matching_receipt_is_not_authenticated(self):
        self.ready()
        manifest = candidate_custody_manifest()
        result = candidate_custody_receipt_comparison(
            manifest=manifest,
            receipt=self.receipt(manifest),
        )
        self.assertTrue(result["receipt_fields_match"])
        self.assertFalse(result["external_custodian_authenticated"])
        self.assertFalse(result["durable_external_storage_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertFalse(result["payroll_access_authorized"])
        self.assertFalse(external_custody_boundary_grants_live_access())

    def test_modified_manifest_digest_is_rejected(self):
        self.ready()
        manifest = candidate_custody_manifest()
        altered = deepcopy(manifest)
        altered["audit_digest"] = "f" * 64
        self.assertIsNone(candidate_custody_receipt_comparison(
            manifest=altered,
            receipt=self.receipt(manifest),
        ))

    def test_wrong_receipt_fingerprint_and_sequence_rejected(self):
        self.ready()
        manifest = candidate_custody_manifest()
        bad = self.receipt(manifest)
        bad["manifest_sha256"] = "0" * 64
        self.assertIsNone(candidate_custody_receipt_comparison(
            manifest=manifest, receipt=bad
        ))
        bad = self.receipt(manifest)
        bad["acknowledged_sequence"] += 1
        self.assertIsNone(candidate_custody_receipt_comparison(
            manifest=manifest, receipt=bad
        ))

    def test_missing_or_forged_authentication_fields_rejected(self):
        self.ready()
        manifest = candidate_custody_manifest()
        forged = self.receipt(manifest)
        forged["external_custodian_authenticated"] = True
        self.assertIsNone(candidate_custody_receipt_comparison(
            manifest=manifest, receipt=forged
        ))
        self.assertIsNone(candidate_custody_receipt_comparison(
            manifest=manifest, receipt={}
        ))

    def test_broken_original_audit_chain_prevents_manifest(self):
        self.ready()
        events = _events()
        altered = deepcopy(events[0])
        altered.payload = {**altered.payload, "tampered": True}
        events[0] = altered
        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertIsNone(candidate_custody_manifest())

    def test_manifest_deterministic_without_new_audit_events(self):
        self.ready()
        first = candidate_custody_manifest()
        second = candidate_custody_manifest()
        self.assertEqual(first, second)
        self.assertEqual(
            first["manifest_sha256"], second["manifest_sha256"]
        )

    def test_manifest_and_comparison_are_read_only(self):
        self.ready()

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
        manifest = candidate_custody_manifest()
        self.assertIsNotNone(
            candidate_custody_receipt_comparison(
                manifest=manifest,
                receipt=self.receipt(manifest),
            )
        )
        self.assertEqual(state(), before)
        self.assertFalse(external_custody_boundary_grants_live_access())