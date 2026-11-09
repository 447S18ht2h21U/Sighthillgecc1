"""Isolated failure-path tests for untrusted custody transport."""
from copy import deepcopy

from django.test import TestCase

from .models import AuditEvent, AuditHead, Outbox
from .payroll_external_custody_boundary_4319 import (
    candidate_custody_manifest,
)
from .payroll_custody_transport_4322 import (
    candidate_custody_object_id,
    candidate_transport_custody_review,
    transport_candidate_grants_live_access,
)
from .test_payroll_custody_readback_4321 import (
    CustodyReadback4321Tests,
)


class CustodyTransport4322Tests(TestCase):
    setUp = CustodyReadback4321Tests.setUp
    assign = CustodyReadback4321Tests.assign
    build = CustodyReadback4321Tests.build
    receipt = CustodyReadback4321Tests.receipt
    make_approved_msr = CustodyReadback4321Tests.make_approved_msr
    prepare_full_payment = (
        CustodyReadback4321Tests.prepare_full_payment
    )
    ready = CustodyReadback4321Tests.ready
    checkpoint = CustodyReadback4321Tests.checkpoint
    minimum = CustodyReadback4321Tests.minimum
    registry = CustodyReadback4321Tests.registry
    custody_receipt = CustodyReadback4321Tests.custody_receipt
    issuer = CustodyReadback4321Tests.issuer
    key = CustodyReadback4321Tests.key
    custodian = CustodyReadback4321Tests.custodian

    def prepared(self):
        manifest = candidate_custody_manifest()
        receipt = self.custody_receipt(manifest)
        response = {
            "object_id": candidate_custody_object_id(manifest),
            "custodian_id": self.custodian,
            "manifest": deepcopy(manifest),
            "receipt": deepcopy(receipt),
        }
        return receipt, response

    def report(self, record, *, fetcher=None, registry=None):
        receipt, response = self.prepared()
        if fetcher is None:
            fetcher = lambda request: deepcopy(response)

        checkpoint = self.checkpoint()

        return candidate_transport_custody_review(
            payment_id=record.pk,
            checkpoint=checkpoint,
            registry=self.registry() if registry is None else registry,
            expected_issuer=self.issuer,
            trusted_minimum=self.minimum(checkpoint),
            receipt=receipt,
            expected_custodian=self.custodian,
            fetcher=fetcher,
        )

    def test_matching_test_transport_still_cannot_authorize(self):
        record, _, _ = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertTrue(result["test_transport_fields_matched"])
        self.assertFalse(result["transport_peer_authenticated"])
        self.assertFalse(result["external_custodian_authenticated"])
        self.assertFalse(result["durable_external_storage_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertFalse(result["payroll_access_authorized"])
        self.assertFalse(transport_candidate_grants_live_access())

    def test_fetcher_failure_and_timeout_denied(self):
        record, _, _ = self.ready()

        def fails(request):
            raise ConnectionError("test provider unavailable")

        def timeout(request):
            raise TimeoutError("test provider timeout")

        self.assertIsNone(self.report(record, fetcher=fails))
        self.assertIsNone(self.report(record, fetcher=timeout))

    def test_missing_and_malformed_response_denied(self):
        record, _, _ = self.ready()

        for response in (None, [], {}, {"object_id": "wrong"}):
            with self.subTest(response=response):
                self.assertIsNone(self.report(
                    record,
                    fetcher=lambda request, value=response: value,
                ))

    def test_substituted_object_id_denied(self):
        record, _, _ = self.ready()
        _, response = self.prepared()
        response["object_id"] = "audit-checkpoint/" + "f" * 64

        self.assertIsNone(self.report(
            record, fetcher=lambda request: response
        ))

    def test_wrong_custodian_denied(self):
        record, _, _ = self.ready()
        _, response = self.prepared()
        response["custodian_id"] = "different-custodian"

        self.assertIsNone(self.report(
            record, fetcher=lambda request: response
        ))

    def test_altered_returned_copy_denied(self):
        record, _, _ = self.ready()
        _, response = self.prepared()
        response["manifest"]["audit_digest"] = "a" * 64

        self.assertIsNone(self.report(
            record, fetcher=lambda request: response
        ))

    def test_revoked_key_denied_even_with_matching_response(self):
        record, _, _ = self.ready()

        self.assertIsNone(self.report(
            record, registry=self.registry(revoked=True)
        ))

    def test_transport_comparison_is_nonmutating(self):
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
        self.assertFalse(transport_candidate_grants_live_access())