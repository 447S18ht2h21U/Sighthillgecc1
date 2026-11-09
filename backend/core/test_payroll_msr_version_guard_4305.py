"""Database-backed payroll MSR version ambiguity safeguards."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
    CustomerPayment,
    MSR,
    Outbox,
    Role,
)
from .payroll_msr_version_guard_4305 import (
    candidate_version_guarded_technical_payment,
    msr_version_guard_grants_live_access,
)
from .test_payroll_earned_technical_candidate_4304 import (
    EarnedTechnicalCandidate4304Tests,
)


class MSRVersionGuard4305Tests(TestCase):
    setUp = EarnedTechnicalCandidate4304Tests.setUp
    assign = EarnedTechnicalCandidate4304Tests.assign
    build = EarnedTechnicalCandidate4304Tests.build
    make_approved_msr = EarnedTechnicalCandidate4304Tests.make_approved_msr
    receipt = EarnedTechnicalCandidate4304Tests.receipt
    prepare_full_payment = EarnedTechnicalCandidate4304Tests.prepare_full_payment

    def candidate(self, record):
        return candidate_version_guarded_technical_payment(
            payment_id=record.pk
        )

    def another_msr(self, status):
        return MSR.objects.create(
            project=self.project,
            number=2,
            status=status,
            snapshot={"total_price": "1200.00"},
            created_by=self.comptroller,
            prepared_by=self.comptroller,
            approved_by=self.comptroller if status == "APPROVED" else None,
        )

    def ready(self):
        self.assign()
        self.prepare_full_payment()
        return self.build()

    def test_single_approved_version_produces_test_only_candidate(self):
        record = self.ready()
        result = self.candidate(record)
        self.assertIsNotNone(result)
        self.assertEqual(result["candidate_role"], Role.TECHNICIAN)
        self.assertEqual(
            result["candidate_receipt_date"],
            "2026-10-15",
        )
        self.assertFalse(msr_version_guard_grants_live_access())

    def test_second_approved_version_fails_closed(self):
        record = self.ready()
        self.another_msr("APPROVED")
        self.assertIsNone(self.candidate(record))

    def test_draft_revision_cannot_change_approved_price(self):
        record = self.ready()
        self.another_msr("DRAFT")
        result = self.candidate(record)
        self.assertIsNotNone(result)
        self.assertEqual(
            result["candidate_receipt_date"],
            "2026-10-15",
        )
        self.assertFalse(msr_version_guard_grants_live_access())

    def test_payment_referencing_other_msr_fails_closed(self):
        record = self.ready()
        alternate = self.another_msr("DRAFT")
        CustomerPayment.objects.create(
            project=self.project,
            msr=alternate,
            kind=CustomerPayment.Kind.FINAL,
            amount=Decimal("100.00"),
            received_date=date(2026, 10, 16),
            payment_reference="MSR4305-OTHER",
            recorded_by=self.comptroller,
        )
        self.assertIsNone(self.candidate(record))

    def test_changed_current_approved_version_fails_closed(self):
        record = self.ready()
        alternate = self.another_msr("APPROVED")
        self.project.current_approved = alternate
        self.project.save(update_fields=["current_approved"])
        self.assertIsNone(self.candidate(record))

    def test_missing_full_payment_fails_closed(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.candidate(record))

    def test_candidate_read_preserves_audit_and_msrs(self):
        record = self.ready()

        def state():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                AuditEvent.objects.count(),
                Outbox.objects.count(),
                list(MSR.objects.filter(
                    project=self.project
                ).values_list(
                    "pk", "number", "status"
                )),
            )

        before = state()
        self.assertIsNotNone(self.candidate(record))
        self.assertEqual(state(), before)