"""Disposable SQLite audit-gated payroll evidence integration tests."""
from copy import copy
from datetime import date

from django.test import TestCase
from unittest.mock import patch

from . import test_payroll_earning_lineage_4306 as fixtures
from .models import (
    AuditEvent,
    AuditHead,
    CustomerPayment,
    MSR,
    Outbox,
)
from .payroll_audit_chain_4309 import _events, _outboxes
from .payroll_audit_verified_lineage_4310 import (
    candidate_audit_verified_earning_lineage,
    audit_verified_lineage_grants_live_access,
)


class AuditVerifiedLineage4310Tests(TestCase):
    setUp = fixtures.EarningLineage4306Tests.setUp
    assign = fixtures.EarningLineage4306Tests.assign
    build = fixtures.EarningLineage4306Tests.build
    receipt = fixtures.EarningLineage4306Tests.receipt
    make_approved_msr = (
        fixtures.EarningLineage4306Tests.make_approved_msr
    )
    prepare_full_payment = (
        fixtures.EarningLineage4306Tests.prepare_full_payment
    )
    ready = fixtures.EarningLineage4306Tests.ready

    def report(self, record):
        return candidate_audit_verified_earning_lineage(
            payment_id=record.pk
        )

    def test_complete_chain_and_evidence_gives_candidate_only(self):
        record, _, _ = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertEqual(result["candidate_receipt_date"], "2026-10-15")
        self.assertTrue(result["database_audit_chain_consistent"])
        self.assertFalse(result["external_audit_anchor_verified"])
        self.assertFalse(result["earning_date_authorized"])
        self.assertEqual(
            result["review_status"],
            "AUDIT_CHECKED_HUMAN_REVIEW_REQUIRED_TEST_ONLY",
        )
        self.assertFalse(audit_verified_lineage_grants_live_access())

    def test_modified_historical_audit_payload_denied(self):
        record, _, _ = self.ready()
        events = _events()
        changed = copy(events[0])
        changed.payload = {**changed.payload, "forged": True}
        events[0] = changed

        with patch(
            "core.payroll_audit_chain_4309._events",
            return_value=events,
        ):
            self.assertIsNone(self.report(record))

    def test_missing_outbox_denied_even_with_valid_receipts(self):
        record, _, _ = self.ready()
        outboxes = _outboxes()

        with patch(
            "core.payroll_audit_chain_4309._outboxes",
            return_value=outboxes[:-1],
        ):
            self.assertIsNone(self.report(record))

    def test_altered_audit_head_denied(self):
        record, _, _ = self.ready()
        altered = copy(AuditHead.objects.get(pk=1))
        altered.sequence += 1

        with patch(
            "core.payroll_audit_chain_4309._head",
            return_value=[altered],
        ):
            self.assertIsNone(self.report(record))

    def test_incomplete_customer_payment_denied(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_missing_technician_assignment_denied(self):
        self.prepare_full_payment()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_conflicting_approved_msr_version_denied(self):
        record, _, _ = self.ready()
        MSR.objects.create(
            project=self.project,
            number=2,
            status="APPROVED",
            snapshot={"total_price": "1200.00"},
            created_by=self.comptroller,
            prepared_by=self.comptroller,
            approved_by=self.comptroller,
        )
        self.assertIsNone(self.report(record))

    def test_audit_verified_candidate_read_is_nonmutating(self):
        record, _, _ = self.ready()

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                AuditEvent.objects.count(),
                Outbox.objects.count(),
                list(CustomerPayment.objects.filter(
                    project=self.project
                ).order_by("pk").values_list(
                    "pk", "status", "amount", "verified_at"
                )),
            )

        before = state()
        self.assertIsNotNone(self.report(record))
        self.assertEqual(before, state())
        self.assertFalse(audit_verified_lineage_grants_live_access())