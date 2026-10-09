from decimal import Decimal
from datetime import date

from django.test import TestCase

from rest_framework.exceptions import ValidationError

from .employee_payroll_services import (
    create_employee_payroll_record,
    approve_employee_payroll_record,
    mark_employee_payroll_paid,
)
from .models import (
    Employee,
    EmployeeCompensationPlan,
    EmployeePayrollRecord,
    Role,
    User,
)


class EmployeePayrollTests(TestCase):

    def setUp(self):

        self.comptroller = User.objects.create_user(
            username='employee_payroll_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.employee = Employee.objects.create(
            employee_number='EMP-001',
            legal_name='Test Employee',
            email='employee@example.com',
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 10, 1),
            created_by=self.comptroller,
        )

        self.compensation_plan = (
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

    def test_creates_draft_employee_payroll_record(self):
        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('2500.00'),
            Decimal('500.00'),
            Decimal('2000.00'),
            {
                'source': 'SALARY_PLAN',
                'gross': '2500.00',
            },
        )

        self.assertEqual(
            record.status,
            EmployeePayrollRecord.Status.DRAFT,
        )

        self.assertEqual(
            record.gross_amount,
            Decimal('2500.00'),
        )

        self.assertEqual(
            record.net_amount,
            Decimal('2000.00'),
        )

        self.assertEqual(
            record.employee_id,
            self.employee.id,
        )

    def test_unapproved_compensation_plan_cannot_create_payroll(self):
        draft_plan = EmployeeCompensationPlan.objects.create(
            employee=self.employee,
            version=2,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            effective_date=date(2026, 10, 15),
            compensation_terms={
                'annual_salary': '70000.00',
            },
            status=(
                EmployeeCompensationPlan.Status.DRAFT
            ),
            created_by=self.comptroller,
        )

        with self.assertRaises(ValidationError):
            create_employee_payroll_record(
                self.comptroller,
                self.employee,
                draft_plan,
                EmployeePayrollRecord.Kind.SALARY,
                date(2026, 10, 15),
                date(2026, 10, 31),
                Decimal('3000.00'),
                Decimal('500.00'),
                Decimal('2500.00'),
                {
                    'source': 'DRAFT_PLAN',
                },
            )

    def test_authorized_user_can_approve_employee_payroll(self):
        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('2500.00'),
            Decimal('500.00'),
            Decimal('2000.00'),
            {
                'source': 'SALARY_PLAN',
            },
        )

        approved = approve_employee_payroll_record(
            self.comptroller,
            record.id,
        )

        self.assertEqual(
            approved.status,
            EmployeePayrollRecord.Status.APPROVED,
        )

        self.assertEqual(
            approved.approved_by_id,
            self.comptroller.id,
        )

        self.assertIsNotNone(
            approved.approved_at,
        )

    def test_approved_employee_payroll_can_be_marked_paid(self):
        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('2500.00'),
            Decimal('500.00'),
            Decimal('2000.00'),
            {
                'source': 'SALARY_PLAN',
            },
        )

        approve_employee_payroll_record(
            self.comptroller,
            record.id,
        )

        paid = mark_employee_payroll_paid(
            self.comptroller,
            record.id,
        )

        self.assertEqual(
            paid.status,
            EmployeePayrollRecord.Status.PAID,
        )

        self.assertIsNotNone(
            paid.paid_at,
        )

    def test_approved_employee_payroll_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('2500.00'),
            Decimal('500.00'),
            Decimal('2000.00'),
            {
                'source': 'SALARY_PLAN',
            },
        )

        approve_employee_payroll_record(
            self.comptroller,
            record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=record.id,
                ).update(
                    net_amount=Decimal('9999.00'),
                )

        record.refresh_from_db()

        self.assertEqual(
            record.status,
            EmployeePayrollRecord.Status.APPROVED,
        )

        self.assertNotEqual(
            record.net_amount,
            Decimal('9999.00'),
        )

    def test_paid_employee_payroll_cannot_be_modified_or_deleted(self):
        from django.db import DatabaseError, transaction

        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal('2500.00'),
            Decimal('500.00'),
            Decimal('2000.00'),
            {
                'source': 'SALARY_PLAN',
            },
        )

        approve_employee_payroll_record(
            self.comptroller,
            record.id,
        )

        paid = mark_employee_payroll_paid(
            self.comptroller,
            record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=paid.id,
                ).update(
                    net_amount=Decimal('9999.00'),
                )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=paid.id,
                ).delete()

        paid.refresh_from_db()

        self.assertEqual(
            paid.status,
            EmployeePayrollRecord.Status.PAID,
        )