from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.db import DatabaseError, transaction

from rest_framework.exceptions import ValidationError

from .commission_record_services import (
    create_commission_records,
    approve_commission_record,
)
from .documents import canonical_hash
from .models import (
    Customer,
    Project,
    MSR,
    CustomerPayment,
    ProjectCostRecord,
    ProjectEvidence,
    CommissionRecord,
    Role,
    User,
)
from .payment_services import verify_customer_payment
from .project_cost_services import approve_project_cost_record


class CommissionRecordTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='commission_record_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.sales_manager = User.objects.create_user(
            username='commission_record_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_associate = User.objects.create_user(
            username='commission_record_sales',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.customer = Customer.objects.create(
            legal_name='Commission Record Customer',
            billing_address='123 Commission Record Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='COMMISSION-RECORD-001',
            customer=self.customer,
            location='Commission Record Location',
            sales_associate=self.sales_associate,
            reviewer=self.sales_manager,
            state='APPROVED',
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '10000.00',
            },
            created_by=self.sales_associate,
            prepared_by=self.sales_associate,
            approved_by=self.comptroller,
        )

        self.project.current_approved = self.msr
        self.project.save(
            update_fields=['current_approved']
        )

        self.cost_record = ProjectCostRecord.objects.create(
            project=self.project,
            msr=self.msr,
            version=1,
            equipment_cost=Decimal('2000.00'),
            material_cost=Decimal('1000.00'),
            dealer_fee=Decimal('500.00'),
            technician_cost=Decimal('750.00'),
            lead_cost=Decimal('3000.00'),
            damon_cost=Decimal('500.00'),
            jerry_cost=Decimal('250.00'),
            created_by=self.sales_manager,
        )

        approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

        self.payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FULL,
            amount=Decimal('10000.00'),
            received_date=date(2026, 10, 8),
            payment_reference='COMMISSION-RECORD-PAYMENT',
            recorded_by=self.sales_manager,
        )

        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

        evidence_data = {
            'source_reference': 'COMMISSION-RECORD-COMPLETE',
            'verification_note': 'Completion verified.',
            'snapshot_sha256': canonical_hash(
                self.msr.snapshot
            ),
            'method': 'MANUAL_ATTESTATION',
            'verified': True,
            'completion_date': '2026-10-08',
            'work_verified': True,
            'permits_inspections_checked': True,
            'exceptions_resolved': True,
        }

        ProjectEvidence.objects.create(
            msr=self.msr,
            kind='WORK_COMPLETION',
            created_by=self.comptroller,
            data=evidence_data,
            digest=canonical_hash(evidence_data),
        )

    def test_eligible_project_creates_draft_commission_records(self):
        records = create_commission_records(
            self.sales_manager,
            self.project.id,
        )

        self.assertEqual(
            len(records),
            2,
        )

        kinds = {
            record.kind
            for record in records
        }

        self.assertEqual(
            kinds,
            {
                CommissionRecord.Kind.RYAN_VARIABLE,
                CommissionRecord.Kind.DOUG_VARIABLE,
            },
        )

        for record in records:
            self.assertEqual(
                record.status,
                CommissionRecord.Status.DRAFT,
            )

            self.assertEqual(
                record.project_id,
                self.project.id,
            )
    def test_ineligible_project_cannot_create_commission_records(self):
        unpaid_project = Project.objects.create(
            code='COMMISSION-RECORD-UNPAID-001',
            customer=self.customer,
            location='Unpaid commission location',
            sales_associate=self.sales_associate,
            reviewer=self.sales_manager,
            state='APPROVED',
        )

        unpaid_msr = MSR.objects.create(
            project=unpaid_project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '10000.00',
            },
            created_by=self.sales_associate,
            prepared_by=self.sales_associate,
            approved_by=self.comptroller,
        )

        unpaid_project.current_approved = unpaid_msr
        unpaid_project.save(
            update_fields=['current_approved']
        )

        with self.assertRaises(ValidationError):
            create_commission_records(
                self.sales_manager,
                unpaid_project.id,
            )

        self.assertEqual(
            CommissionRecord.objects.count(),
            0,
        )
    def test_authorized_user_can_approve_commission_record(self):
        records = create_commission_records(
            self.sales_manager,
            self.project.id,
        )

        record = records[0]

        approved = approve_commission_record(
            self.sales_manager,
            record.id,
        )

        self.assertEqual(
            approved.status,
            CommissionRecord.Status.APPROVED,
        )

        self.assertEqual(
            approved.approved_by_id,
            self.sales_manager.id,
        )

        self.assertIsNotNone(
            approved.approved_at,
        )

    def test_approved_commission_record_cannot_be_modified(self):
        records = create_commission_records(
            self.sales_manager,
            self.project.id,
        )

        record = approve_commission_record(
            self.sales_manager,
            records[0].id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                CommissionRecord.objects.filter(
                    pk=record.id,
                ).update(
                    final_amount=Decimal('9999.00'),
                )

        record.refresh_from_db()

        self.assertEqual(
            record.status,
            CommissionRecord.Status.APPROVED,
        )

        self.assertNotEqual(
            record.final_amount,
            Decimal('9999.00'),
        )

    def test_approved_commission_record_cannot_be_deleted(self):
        records = create_commission_records(
            self.sales_manager,
            self.project.id,
        )

        record = approve_commission_record(
            self.sales_manager,
            records[0].id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                CommissionRecord.objects.filter(
                    pk=record.id,
                ).delete()

        record.refresh_from_db()

        self.assertEqual(
            record.status,
            CommissionRecord.Status.APPROVED,
        )