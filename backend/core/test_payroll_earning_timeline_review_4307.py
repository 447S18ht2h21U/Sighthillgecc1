"""Database-backed tests for provisional earning-date timeline review."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
    CustomerPayment,
    CustomerPaymentAdjustment,
    Outbox,
)
from .payment_services import approve_customer_payment_adjustment
from .payroll_earning_timeline_review_4307 import (
    _date_issue,
    candidate_earning_timeline_review,
    timeline_review_grants_live_access,
)
from .test_payroll_earning_lineage_4306 import EarningLineage4306Tests


class EarningTimelineReview4307Tests(TestCase):
    setUp = EarningLineage4306Tests.setUp
    assign = EarningLineage4306Tests.assign
    build = EarningLineage4306Tests.build
    ready = EarningLineage4306Tests.ready
    make_approved_msr = EarningLineage4306Tests.make_approved_msr
    prepare_full_payment = EarningLineage4306Tests.prepare_full_payment
    receipt = EarningLineage4306Tests.receipt

    def report(self, record):
        return candidate_earning_timeline_review(
            payment_id=record.pk,
        )

    def test_distinct_receipt_and_bank_dates_flagged(self):
        record, _, _ = self.ready()
        result = self.report(record)
        self.assertIsNotNone(result)
        self.assertEqual(result["candidate_receipt_date"], "2026-10-15")
        self.assertEqual(len(result["reviewed_receipts"]), 2)
        self.assertTrue(result["timing_difference_present"])
        self.assertTrue(all(
            item["timing_issue"] == "BANK_AVAILABLE_AFTER_RECEIPT"
            for item in result["reviewed_receipts"]
        ))

    def test_no_timeline_date_grants_earning_authority(self):
        record, _, _ = self.ready()
        result = self.report(record)
        self.assertFalse(result["earning_date_authorized"])
        self.assertEqual(
            result["review_status"],
            "HUMAN_REVIEW_REQUIRED_TEST_ONLY",
        )
        self.assertFalse(timeline_review_grants_live_access())

    def test_same_day_and_out_of_order_dates_distinguished(self):
        first = date(2026, 10, 15)
        later = date(2026, 10, 16)
        earlier = date(2026, 10, 14)
        self.assertIsNone(_date_issue(first, first))
        self.assertEqual(
            _date_issue(first, later),
            "BANK_AVAILABLE_AFTER_RECEIPT",
        )
        self.assertEqual(
            _date_issue(first, earlier),
            "BANK_DATE_BEFORE_RECEIPT",
        )
        self.assertEqual(_date_issue(None, later), "INVALID_DATE")

    def test_incomplete_customer_payment_has_no_review(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_missing_technician_assignment_has_no_review(self):
        self.prepare_full_payment()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_approved_refund_requires_separate_review(self):
        record, deposit, _ = self.ready()
        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=deposit,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("25.00"),
            adjustment_date=date(2026, 11, 5),
            adjustment_reference="TIMELINE4307-REFUND",
            reason="Isolated test-only adjustment",
            recorded_by=self.comptroller,
        )
        approve_customer_payment_adjustment(
            self.comptroller, adjustment.pk,
        )
        self.assertIsNone(self.report(record))

    def test_timeline_read_does_not_write_database(self):
        record, _, _ = self.ready()

        def snapshot():
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

        before = snapshot()
        self.assertIsNotNone(self.report(record))
        self.assertEqual(snapshot(), before)