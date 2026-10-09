from decimal import Decimal
from datetime import date

from django.test import TestCase

from rest_framework.exceptions import ValidationError

from .contractor_payment_services import (
    approve_contractor_payment_record,
    mark_contractor_payment_paid,
    create_contractor_payment_record,
)
from .employee_payroll_services import (
    approve_employee_payroll_record,
    mark_employee_payroll_paid,
    create_employee_payroll_record,
)
from .payroll_summary_services import (
    create_payroll_summary,
    approve_payroll_summary,
)
from .models import (
    Contractor,
    ContractorEngagement,
    ContractorCompensationPlan,
    ContractorPaymentRecord,
    Employee,
    EmployeeCompensationPlan,
    EmployeePayrollRecord,
    PayrollSummary,
    Role,
    User,
)


class PayrollSummaryTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='payroll_summary_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.contractor = Contractor.objects.create(
            contractor_number='CTR-SUM-001',
            legal_name='Summary Contractor',
            created_by=self.comptroller,
        )

        self.engagement = ContractorEngagement.objects.create(
            contractor=self.contractor,
            engagement_code='ENG-SUM-001',
            role_description='Installer',
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.comptroller,
        )

        self.contractor_plan = (
            ContractorCompensationPlan.objects.create(
                engagement=self.engagement,
                version=1,
                effective_date=date(2026, 10, 1),
                compensation_terms={
                    'amount': '500.00',
                },
                status=(
                    ContractorCompensationPlan.Status.APPROVED
                ),
                created_by=self.comptroller,
                approved_by=self.comptroller,
            )
        )

        contractor_payment = (
            create_contractor_payment_record(
                self.comptroller,
                self.engagement,
                self.contractor_plan,
                ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
                date(2026, 10, 1),
                date(2026, 10, 15),
                Decimal('500.00'),
                Decimal('0.00'),
                Decimal('500.00'),
                {
                    'source': 'CONTRACTOR_PLAN',
                },
            )
        )

        approve_contractor_payment_record(
            self.comptroller,
            contractor_payment.id,
        )

        mark_contractor_payment_paid(
            self.comptroller,
            contractor_payment.id,
        )

        self.employee = Employee.objects.create(
            employee_number='EMP-SUM-001',
            legal_name='Summary Employee',
            hire_date=date(2026, 10, 1),
            status=Employee.Status.ACTIVE,
            created_by=self.comptroller,
        )

        self.employee_plan = (
            EmployeeCompensationPlan.objects.create(
                employee=self.employee,
                version=1,
                kind=EmployeeCompensationPlan.Kind.SALARY,
                effective_date=date(2026, 10, 1),
                compensation_terms={
                    'annual_salary': '60000.00',
                },
                status=(
                    EmployeeCompensationPlan.Status.APPROVED
                ),
                created_by=self.comptroller,
                approved_by=self.comptroller,
            )
        )

        employee_payroll = (
            create_employee_payroll_record(
                self.comptroller,
                self.employee,
                self.employee_plan,
                EmployeePayrollRecord.Kind.SALARY,
                date(2026, 10, 1),
                date(2026, 10, 15),
                Decimal('2500.00'),
                Decimal('500.00'),
                Decimal('2000.00'),
                {
                    'source': 'EMPLOYEE_PLAN',
                },
            )
        )

        approve_employee_payroll_record(
            self.comptroller,
            employee_payroll.id,
        )

        mark_employee_payroll_paid(
            self.comptroller,
            employee_payroll.id,
        )

    def test_creates_payroll_summary_from_paid_records(self):
        summary = create_payroll_summary(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        self.assertEqual(
            summary.status,
            PayrollSummary.Status.DRAFT,
        )

        self.assertEqual(
            summary.contractor_total,
            Decimal('500.00'),
        )

        self.assertEqual(
            summary.employee_total,
            Decimal('2000.00'),
        )

        self.assertEqual(
            summary.total_payroll_expense,
            Decimal('2500.00'),
        )

        self.assertEqual(
            len(summary.summary_snapshot['contractor_records']),
            1,
        )

        self.assertEqual(
            len(summary.summary_snapshot['employee_records']),
            1,
        )

    def test_duplicate_payroll_summary_period_is_rejected(self):
        create_payroll_summary(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        with self.assertRaises(ValidationError):
            create_payroll_summary(
                self.comptroller,
                date(2026, 10, 1),
                date(2026, 10, 15),
            )

    def test_authorized_user_can_approve_payroll_summary(self):
        summary = create_payroll_summary(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approved = approve_payroll_summary(
            self.comptroller,
            summary.id,
        )

        self.assertEqual(
            approved.status,
            PayrollSummary.Status.APPROVED,
        )

        self.assertEqual(
            approved.approved_by_id,
            self.comptroller.id,
        )

        self.assertIsNotNone(
            approved.approved_at,
        )

    def test_approved_payroll_summary_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        summary = create_payroll_summary(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approve_payroll_summary(
            self.comptroller,
            summary.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                PayrollSummary.objects.filter(
                    pk=summary.id,
                ).update(
                    total_payroll_expense=Decimal('9999.00'),
                )

        summary.refresh_from_db()

        self.assertEqual(
            summary.status,
            PayrollSummary.Status.APPROVED,
        )

        self.assertNotEqual(
            summary.total_payroll_expense,
            Decimal('9999.00'),
        )

    def test_approved_payroll_summary_cannot_be_deleted(self):
        from django.db import DatabaseError, transaction

        summary = create_payroll_summary(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 15),
        )

        approve_payroll_summary(
            self.comptroller,
            summary.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                PayrollSummary.objects.filter(
                    pk=summary.id,
                ).delete()

        summary.refresh_from_db()

        self.assertEqual(
            summary.status,
            PayrollSummary.Status.APPROVED,
        )