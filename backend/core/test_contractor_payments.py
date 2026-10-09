from decimal import Decimal
from datetime import date

from django.test import TestCase

from rest_framework.exceptions import ValidationError

from .contractor_payment_services import (
    create_contractor_payment_record,
    approve_contractor_payment_record,
    mark_contractor_payment_paid,
)
from .models import (
    Contractor,
    ContractorEngagement,
    ContractorCompensationPlan,
    ContractorPaymentRecord,
    Role,
    User,
)


class ContractorPaymentTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='payment_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.sales_manager = User.objects.create_user(
            username='payment_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.contractor = Contractor.objects.create(
            contractor_number='CTR-001',
            legal_name='Test Contractor',
            email='contractor@example.com',
            created_by=self.comptroller,
        )

        self.engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code='ENG-001',
            role_description='Installation Contractor',
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )

        self.compensation_plan = (
            ContractorCompensationPlan.objects.create(
                engagement=self.engagement,
                version=1,
                effective_date=date(2026, 10, 1),
                compensation_terms={
                    'type': 'FIXED_COMPENSATION',
                    'amount': '500.00',
                },
                status=(
                    ContractorCompensationPlan.Status.APPROVED
                ),
                created_by=self.comptroller,
                approved_by=self.comptroller,
            )
        )

    def test_creates_draft_contractor_payment_record(self):
        record = create_contractor_payment_record(
            self.sales_manager,
            self.engagement,
            self.compensation_plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('500.00'),
            Decimal('0.00'),
            Decimal('500.00'),
            {
                'source': 'COMPENSATION_PLAN',
                'amount': '500.00',
            },
        )

        self.assertEqual(
            record.status,
            ContractorPaymentRecord.Status.DRAFT,
        )

        self.assertEqual(
            record.final_amount,
            Decimal('500.00'),
        )

        self.assertEqual(
            record.engagement_id,
            self.engagement.id,
        )

    def test_unapproved_compensation_plan_cannot_create_payment(self):
        draft_plan = ContractorCompensationPlan.objects.create(
            engagement=self.engagement,
            version=2,
            effective_date=date(2026, 10, 15),
            compensation_terms={
                'type': 'FIXED_COMPENSATION',
                'amount': '700.00',
            },
            status=(
                ContractorCompensationPlan.Status.DRAFT
            ),
            created_by=self.comptroller,
        )

        with self.assertRaises(ValidationError):
            create_contractor_payment_record(
                self.sales_manager,
                self.engagement,
                draft_plan,
                ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
                date(2026, 10, 15),
                date(2026, 10, 31),
                Decimal('700.00'),
                Decimal('0.00'),
                Decimal('700.00'),
                {
                    'source': 'DRAFT_PLAN',
                },
            )

    def test_authorized_user_can_approve_contractor_payment(self):
        record = create_contractor_payment_record(
            self.sales_manager,
            self.engagement,
            self.compensation_plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('500.00'),
            Decimal('0.00'),
            Decimal('500.00'),
            {
                'source': 'COMPENSATION_PLAN',
            },
        )

        approved = approve_contractor_payment_record(
            self.sales_manager,
            record.id,
        )

        self.assertEqual(
            approved.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

        self.assertEqual(
            approved.approved_by_id,
            self.sales_manager.id,
        )

        self.assertIsNotNone(
            approved.approved_at,
        )

    def test_approved_contractor_payment_can_be_marked_paid(self):
        record = create_contractor_payment_record(
            self.sales_manager,
            self.engagement,
            self.compensation_plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('500.00'),
            Decimal('0.00'),
            Decimal('500.00'),
            {
                'source': 'COMPENSATION_PLAN',
            },
        )

        approve_contractor_payment_record(
            self.sales_manager,
            record.id,
        )

        paid = mark_contractor_payment_paid(
            self.comptroller,
            record.id,
        )

        self.assertEqual(
            paid.status,
            ContractorPaymentRecord.Status.PAID,
        )

        self.assertIsNotNone(
            paid.paid_at,
        )

    def test_approved_contractor_payment_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        record = create_contractor_payment_record(
            self.sales_manager,
            self.engagement,
            self.compensation_plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('500.00'),
            Decimal('0.00'),
            Decimal('500.00'),
            {
                'source': 'COMPENSATION_PLAN',
            },
        )

        approve_contractor_payment_record(
            self.sales_manager,
            record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ContractorPaymentRecord.objects.filter(
                    pk=record.id,
                ).update(
                    final_amount=Decimal('9999.00'),
                )

        record.refresh_from_db()

        self.assertEqual(
            record.status,
            ContractorPaymentRecord.Status.APPROVED,
        )

        self.assertNotEqual(
            record.final_amount,
            Decimal('9999.00'),
        )

    def test_paid_contractor_payment_cannot_be_modified_or_deleted(self):
        from django.db import DatabaseError, transaction

        record = create_contractor_payment_record(
            self.sales_manager,
            self.engagement,
            self.compensation_plan,
            ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('500.00'),
            Decimal('0.00'),
            Decimal('500.00'),
            {
                'source': 'COMPENSATION_PLAN',
            },
        )

        approve_contractor_payment_record(
            self.sales_manager,
            record.id,
        )

        paid = mark_contractor_payment_paid(
            self.comptroller,
            record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ContractorPaymentRecord.objects.filter(
                    pk=paid.id,
                ).update(
                    final_amount=Decimal('9999.00'),
                )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ContractorPaymentRecord.objects.filter(
                    pk=paid.id,
                ).delete()

        paid.refresh_from_db()

        self.assertEqual(
            paid.status,
            ContractorPaymentRecord.Status.PAID,
        )