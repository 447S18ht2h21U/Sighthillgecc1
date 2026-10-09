from decimal import Decimal
from datetime import date

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .commission_record_services import (
    create_commission_records,
    approve_commission_record,
)
from .commission_report_services import (
    create_commission_report,
    approve_commission_report,
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
    CommissionReport,
    Role,
    User,
)
from .payment_services import verify_customer_payment
from .project_cost_services import approve_project_cost_record


class CommissionReportTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='report_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.sales_manager = User.objects.create_user(
            username='report_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_associate = User.objects.create_user(
            username='report_sales',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.customer = Customer.objects.create(
            legal_name='Commission Report Customer',
            billing_address='123 Report Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='REPORT-001',
            customer=self.customer,
            location='Report Location',
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

        payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FULL,
            amount=Decimal('10000.00'),
            received_date=date(2026, 10, 8),
            payment_reference='REPORT-PAYMENT-001',
            recorded_by=self.sales_manager,
        )

        verify_customer_payment(
            self.comptroller,
            payment.id,
        )

        evidence_data = {
            'source_reference': 'REPORT-COMPLETE-001',
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

        records = create_commission_records(
            self.sales_manager,
            self.project.id,
        )

        for record in records:
            approve_commission_record(
                self.sales_manager,
                record.id,
            )

    def test_creates_biweekly_commission_report(self):
        report = create_commission_report(
            self.sales_manager,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        self.assertEqual(
            report.status,
            CommissionReport.Status.DRAFT,
        )

        self.assertEqual(
            report.period_start,
            date(2026, 10, 1),
        )

        self.assertEqual(
            report.period_end,
            date(2026, 10, 15),
        )

        self.assertEqual(
            report.report_snapshot['record_count'],
            2,
        )

        self.assertEqual(
            len(report.report_snapshot['records']),
            2,
        )

    def test_duplicate_commission_report_period_is_rejected(self):
        create_commission_report(
            self.sales_manager,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        with self.assertRaises(ValidationError):
            create_commission_report(
                self.sales_manager,
                date(2026, 10, 1),
                date(2026, 10, 15),
            )

    def test_authorized_user_can_approve_commission_report(self):
        report = create_commission_report(
            self.sales_manager,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approved = approve_commission_report(
            self.sales_manager,
            report.id,
        )

        self.assertEqual(
            approved.status,
            CommissionReport.Status.APPROVED,
        )

        self.assertEqual(
            approved.approved_by_id,
            self.sales_manager.id,
        )

        self.assertIsNotNone(
            approved.approved_at,
        )

    def test_approved_commission_report_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        report = create_commission_report(
            self.sales_manager,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        report = approve_commission_report(
            self.sales_manager,
            report.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                CommissionReport.objects.filter(
                    pk=report.id,
                ).update(
                    report_snapshot={
                        'tampered': True,
                    },
                )

        report.refresh_from_db()

        self.assertEqual(
            report.status,
            CommissionReport.Status.APPROVED,
        )

    def test_approved_commission_report_cannot_be_deleted(self):
        from django.db import DatabaseError, transaction

        report = create_commission_report(
            self.sales_manager,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        report = approve_commission_report(
            self.sales_manager,
            report.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                CommissionReport.objects.filter(
                    pk=report.id,
                ).delete()

        report.refresh_from_db()

        self.assertEqual(
            report.status,
            CommissionReport.Status.APPROVED,
        )