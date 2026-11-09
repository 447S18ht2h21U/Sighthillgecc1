"""Database-backed provisional earning-date evidence lineage tests."""
from decimal import Decimal

from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
    CustomerPayment,
    Outbox,
    Role,
)
from .payroll_earning_lineage_4306 import (
    candidate_earning_lineage,
    earning_lineage_grants_live_access,
)
from .test_payroll_earned_technical_candidate_4304 import (
    EarnedTechnicalCandidate4304Tests,
)


class EarningLineage4306Tests(TestCase):
    setUp = EarnedTechnicalCandidate4304Tests.setUp
    assign = EarnedTechnicalCandidate4304Tests.assign
    build = EarnedTechnicalCandidate4304Tests.build
    make_approved_msr = EarnedTechnicalCandidate4304Tests.make_approved_msr
    receipt = EarnedTechnicalCandidate4304Tests.receipt
    prepare_full_payment = (
        EarnedTechnicalCandidate4304Tests.prepare_full_payment
    )

    def ready(self):
        self.assign()
        deposit, final = self.prepare_full_payment()
        return self.build(), deposit, final

    def report(self, record):
        return candidate_earning_lineage(payment_id=record.pk)

    def test_trace_identifies_msr_and_both_bank_confirmations(self):
        record, deposit, final = self.ready()
        result = self.report(record)

        self.assertIsNotNone(result)
        self.assertEqual(result["candidate_role"], Role.TECHNICIAN)
        self.assertEqual(result["approved_msr_id"], str(self.project.current_approved_id))
        self.assertEqual(result["approved_msr_version"], 1)
        self.assertEqual(result["approved_total"], "1000.00")
        self.assertEqual(result["candidate_receipt_date"], "2026-10-15")
        self.assertEqual(len(result["supporting_receipts"]), 2)

        receipts = {
            item["customer_payment_id"]: item
            for item in result["supporting_receipts"]
        }
        self.assertEqual(
            set(receipts),
            {str(deposit.pk), str(final.pk)},
        )
        for item in receipts.values():
            self.assertTrue(item["bank_confirmation_id"])
        self.assertEqual(
            result["evidence_status"],
            "TEST_ONLY_TRACE_NOT_FINAL_AUTHORITY",
        )
        self.assertFalse(earning_lineage_grants_live_access())

    def test_partial_payment_has_no_trace(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_unconfirmed_final_receipt_has_no_trace(self):
        self.assign()
        self.prepare_full_payment(final_bank=False)
        record = self.build()
        self.assertIsNone(self.report(record))

    def test_unlinked_contractor_has_no_trace(self):
        self.assign()
        self.prepare_full_payment()
        record = self.build(linked=False)
        self.assertIsNone(self.report(record))

    def test_altered_receipt_reference_has_no_trace(self):
        record, _, final = self.ready()
        CustomerPayment.objects.filter(pk=final.pk).update(
            payment_reference="ALTERED-REFERENCE"
        )
        self.assertIsNone(self.report(record))

    def test_trace_does_not_modify_financial_or_audit_records(self):
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
                    "pk", "status", "verified_at", "amount"
                )),
            )

        before = state()
        self.assertIsNotNone(self.report(record))
        self.assertEqual(state(), before)
        self.assertFalse(earning_lineage_grants_live_access())