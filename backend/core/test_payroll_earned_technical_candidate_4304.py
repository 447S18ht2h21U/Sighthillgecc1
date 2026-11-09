"""Database-backed integrated earning-date and technician candidate tests."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import (
    AuditEvent,
    AuditHead,
    CustomerPayment,
    CustomerPaymentAdjustment,
    ContractorPaymentRecord,
    MSR,
    Outbox,
    Role,
)
from .payment_services import (
    approve_customer_payment_adjustment,
    verify_customer_payment,
)
from .customer_payment_bank_confirmation_services import (
    confirm_customer_payment_bank_availability,
)
from .payroll_earned_technical_candidate_4304 import (
    candidate_earned_technical_payment,
    earned_technical_candidate_grants_live_access,
)
from .test_payroll_payment_technical_link_4300 import (
    PaymentTechnicalLink4300Tests,
)


class EarnedTechnicalCandidate4304Tests(TestCase):
    setUp = PaymentTechnicalLink4300Tests.setUp
    assign = PaymentTechnicalLink4300Tests.assign
    build = PaymentTechnicalLink4300Tests.build

    def make_approved_msr(self, project=None):
        if project is None:
            project = self.project

        msr = MSR.objects.create(
            project=project,
            number=1,
            status="APPROVED",
            snapshot={"total_price": "1000.00"},
            created_by=self.comptroller,
            prepared_by=self.comptroller,
            approved_by=self.comptroller,
        )
        project.current_approved = msr
        project.save(update_fields=["current_approved"])
        return msr

    def receipt(self, msr, *, amount, received, reference,
                kind, verify=True, bank=True):
        payment = CustomerPayment.objects.create(
            project=msr.project,
            msr=msr,
            kind=kind,
            amount=Decimal(amount),
            received_date=received,
            payment_reference=reference,
            recorded_by=self.comptroller,
        )

        if verify:
            verify_customer_payment(self.comptroller, payment.pk)

        if verify and bank:
            confirm_customer_payment_bank_availability(
                actor=self.comptroller,
                payment_id=payment.pk,
                bank_reference="BANK-" + reference,
                confirmation_date=timezone.localdate(),
                confirmation_method="Isolated test bank review",
                confirmation_note="Disposable test evidence only.",
            )

        return payment

    def prepare_full_payment(self, *, project=None, final_verify=True,
                             final_bank=True, final_amount="500.00"):
        msr = self.make_approved_msr(project=project)

        deposit = self.receipt(
            msr,
            amount="500.00",
            received=date(2026, 10, 8),
            reference="EARN4304-DEPOSIT",
            kind=CustomerPayment.Kind.DEPOSIT,
        )

        final = self.receipt(
            msr,
            amount=final_amount,
            received=date(2026, 10, 15),
            reference="EARN4304-FINAL",
            kind=CustomerPayment.Kind.FINAL,
            verify=final_verify,
            bank=final_bank,
        )
        return deposit, final

    def candidate(self, record):
        return candidate_earned_technical_payment(
            payment_id=record.pk
        )

    def test_matching_project_receipts_and_assignment_candidate(self):
        self.assign()
        self.prepare_full_payment()
        record = self.build()

        result = self.candidate(record)

        self.assertIsNotNone(result)
        self.assertEqual(result["project_id"], str(self.project.pk))
        self.assertEqual(result["candidate_role"], Role.TECHNICIAN)
        self.assertEqual(
            result["candidate_receipt_date"], "2026-10-15"
        )
        self.assertEqual(
            result["status"], "TEST_ONLY_UNAPPROVED_CANDIDATE"
        )
        self.assertFalse(earned_technical_candidate_grants_live_access(
            payment_id=record.pk
        ))

    def test_partial_customer_payment_does_not_classify(self):
        self.assign()
        self.make_approved_msr()
        record = self.build()
        self.assertIsNone(self.candidate(record))

    def test_pending_final_payment_does_not_classify(self):
        self.assign()
        self.prepare_full_payment(final_verify=False)
        record = self.build()
        self.assertIsNone(self.candidate(record))

    def test_missing_final_bank_confirmation_does_not_classify(self):
        self.assign()
        self.prepare_full_payment(final_bank=False)
        record = self.build()
        self.assertIsNone(self.candidate(record))

    def test_missing_technician_assignment_does_not_classify(self):
        self.prepare_full_payment()
        record = self.build()
        self.assertIsNone(self.candidate(record))

    def test_missing_contractor_user_link_does_not_classify(self):
        self.assign()
        self.prepare_full_payment()
        record = self.build(linked=False)
        self.assertIsNone(self.candidate(record))

    def test_draft_contractor_payment_does_not_classify(self):
        self.assign()
        self.prepare_full_payment()
        record = self.build(approved=False)
        self.assertIsNone(self.candidate(record))

    def test_other_project_customer_receipts_do_not_classify(self):
        self.assign()
        self.prepare_full_payment(project=self.other_project)
        record = self.build()
        self.assertIsNone(self.candidate(record))

    def test_approved_refund_denies_and_candidate_read_is_read_only(self):
        self.assign()
        deposit, _ = self.prepare_full_payment()
        record = self.build()

        def snapshot():
            return (
                tuple(AuditHead.objects.values_list(
                    "sequence", "digest"
                ).get(pk=1)),
                AuditEvent.objects.count(),
                Outbox.objects.count(),
                ContractorPaymentRecord.objects.values_list(
                    "status", "approved_at", "paid_at"
                ).get(pk=record.pk),
            )

        before = snapshot()
        self.assertIsNotNone(self.candidate(record))
        self.assertEqual(snapshot(), before)

        adjustment = CustomerPaymentAdjustment.objects.create(
            payment=deposit,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal("25.00"),
            adjustment_date=timezone.localdate(),
            adjustment_reference="EARN4304-REFUND",
            reason="Test-only later refund",
            recorded_by=self.comptroller,
        )
        approve_customer_payment_adjustment(
            self.comptroller, adjustment.pk
        )
        self.assertIsNone(self.candidate(record))
        self.assertFalse(earned_technical_candidate_grants_live_access())