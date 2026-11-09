"""Disposable database-backed payment and technician linkage tests."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from .contractor_payment_services import (
    approve_contractor_payment_record,
    create_contractor_payment_record,
)
from .models import (
    AuditEvent,
    AuditHead,
    Contractor,
    ContractorCompensationPlan,
    ContractorEngagement,
    ContractorPaymentRecord,
    Outbox,
    Role,
    User,
)
from .payroll_payment_technical_link_4300 import (
    candidate_technical_payment_link,
    technical_payment_link_grants_live_access,
)
from .test_payroll_technical_provenance_4296 import (
    DatabaseTechnicalProvenance4296Tests,
)


EARNED = date(2026, 10, 12)


class PaymentTechnicalLink4300Tests(TestCase):
    setUp = DatabaseTechnicalProvenance4296Tests.setUp
    assign = DatabaseTechnicalProvenance4296Tests.assign

    def build(self, *, linked=True, project=True, matching_plan=True,
              approved=True):
        ceo = User.objects.create_user(
            username="payment_link_4300_ceo",
            role=Role.CEO,
        )
        contractor = Contractor.objects.create(
            contractor_number="CTR-LINK-4300",
            legal_name="Test-only linked technician",
            user=self.technician if linked else None,
            created_by=self.comptroller,
        )
        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code="ENG-LINK-4300",
            role_description="Free text is not classification",
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )
        plan_engagement = engagement

        if not matching_plan:
            other_contractor = Contractor.objects.create(
                contractor_number="CTR-LINK-4300-OTHER",
                legal_name="Other test-only contractor",
                created_by=self.comptroller,
            )
            plan_engagement = ContractorEngagement.objects.create(
                contractor=other_contractor,
                engagement_code="ENG-LINK-4300-OTHER",
                role_description="Other",
                status=ContractorEngagement.Status.ACTIVE,
                created_by=self.comptroller,
            )

        plan = ContractorCompensationPlan.objects.create(
            engagement=plan_engagement,
            version=1,
            status=ContractorCompensationPlan.Status.APPROVED,
            effective_date=date(2026, 10, 1),
            compensation_terms={"amount": "125.00"},
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )
        record = create_contractor_payment_record(
            self.comptroller,
            engagement,
            plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 5),
            date(2026, 10, 18),
            Decimal("125.00"),
            Decimal("0.00"),
            Decimal("125.00"),
            {"source": "TEST_ONLY"},
            project=self.project if project else None,
        )
        if approved:
            approve_contractor_payment_record(ceo, record.pk)
        return record

    def classify(self, record, earned=EARNED):
        return candidate_technical_payment_link(
            payment_id=record.pk,
            earned_on=earned,
        )

    def test_matching_audited_payment_and_assignment_is_candidate_only(self):
        self.assign()
        record = self.build()
        self.assertEqual(self.classify(record), Role.TECHNICIAN)
        self.assertFalse(technical_payment_link_grants_live_access(
            payment_id=record.pk,
            earned_on=EARNED,
        ))

    def test_draft_payment_is_not_candidate(self):
        self.assign()
        record = self.build(approved=False)
        self.assertIsNone(self.classify(record))

    def test_payment_without_project_is_not_candidate(self):
        self.assign()
        record = self.build(project=False)
        self.assertIsNone(self.classify(record))

    def test_unlinked_contractor_is_not_candidate(self):
        self.assign()
        record = self.build(linked=False)
        self.assertIsNone(self.classify(record))

    def test_mismatched_compensation_plan_is_rejected(self):
        self.assign()
        record = self.build(matching_plan=False)
        self.assertIsNone(self.classify(record))

    def test_missing_matching_assignment_is_rejected(self):
        record = self.build()
        self.assertIsNone(self.classify(record))

    def test_earning_date_not_inferred_from_pay_period(self):
        self.assign()
        record = self.build()
        self.assertIsNone(self.classify(record, earned=None))
        self.assertIsNone(self.classify(
            record, earned=date(2026, 10, 9)
        ))
        self.assertEqual(
            record.payment_period_end,
            date(2026, 10, 18),
        )
        self.assertFalse(technical_payment_link_grants_live_access(
            earned_on=record.payment_period_end,
        ))

    def test_candidate_read_does_not_change_records_or_audit(self):
        self.assign()
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
        self.assertEqual(self.classify(record), Role.TECHNICIAN)
        self.assertEqual(snapshot(), before)