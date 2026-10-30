"""Database-level regression tests for payroll compensation relationships.

These tests intentionally bypass the payroll service to verify migration
0068 guards at the persistence boundary. Django uses an isolated test DB.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from . import test_employee_payroll as payroll_fixtures
from .models import Employee, EmployeeCompensationPlan, EmployeePayrollRecord


class EmployeePayrollDatabaseRelationshipTests(TestCase):
    def setUp(self):
        payroll_fixtures.EmployeePayrollTests.setUp(self)

    def make_plan(self, employee=None, effective_date=None, status=None, version=2):
        return EmployeeCompensationPlan.objects.create(
            employee=employee or self.employee,
            version=version,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            effective_date=effective_date or date(2026, 11, 1),
            compensation_terms={"annual_salary": "65000.00"},
            status=status or EmployeeCompensationPlan.Status.APPROVED,
            created_by=self.comptroller,
            approved_by=self.comptroller if (
                status != EmployeeCompensationPlan.Status.DRAFT
            ) else None,
        )

    def make_payroll(
        self,
        employee=None,
        plan=None,
        start=None,
        end=None,
    ):
        return EmployeePayrollRecord.objects.create(
            employee=employee or self.employee,
            compensation_plan=plan or self.compensation_plan,
            kind=EmployeePayrollRecord.Kind.SALARY,
            payroll_period_start=start or date(2026, 10, 10),
            payroll_period_end=end or date(2026, 10, 20),
            gross_amount=Decimal("1000.00"),
            deduction_amount=Decimal("100.00"),
            net_amount=Decimal("900.00"),
            calculation_snapshot={"test": "direct_database_insert"},
            created_by=self.comptroller,
        )

    def expect_database_rejection(self, operation):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                operation()

    def test_direct_insert_accepts_valid_plan(self):
        payroll = self.make_payroll()
        self.assertEqual(payroll.status, EmployeePayrollRecord.Status.DRAFT)

    def test_direct_insert_rejects_other_employee_plan(self):
        other = Employee.objects.create(
            employee_number="EMP-OTHER-DB",
            legal_name="Other Payroll Employee",
            email="other-payroll-db@example.com",
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 10, 1),
            created_by=self.comptroller,
        )
        other_plan = self.make_plan(
            employee=other,
            effective_date=date(2026, 10, 1),
        )
        self.expect_database_rejection(
            lambda: self.make_payroll(plan=other_plan)
        )

    def test_direct_insert_rejects_unapproved_plan(self):
        draft_plan = self.make_plan(
            effective_date=date(2026, 10, 1),
            status=EmployeeCompensationPlan.Status.DRAFT,
        )
        self.expect_database_rejection(
            lambda: self.make_payroll(plan=draft_plan)
        )

    def test_direct_insert_rejects_future_plan(self):
        future_plan = self.make_plan(
            effective_date=date(2026, 11, 1),
        )
        self.expect_database_rejection(
            lambda: self.make_payroll(plan=future_plan)
        )

    def test_direct_insert_rejects_period_crossing_plan_change(self):
        self.make_plan(effective_date=date(2026, 11, 1))
        self.expect_database_rejection(
            lambda: self.make_payroll(
                start=date(2026, 10, 25),
                end=date(2026, 11, 5),
            )
        )

    def test_direct_insert_rejects_outdated_plan(self):
        self.make_plan(effective_date=date(2026, 11, 1))
        self.expect_database_rejection(
            lambda: self.make_payroll(
                start=date(2026, 11, 5),
                end=date(2026, 11, 15),
            )
        )

    def test_direct_update_rejects_wrong_employee_plan(self):
        payroll = self.make_payroll()
        other = Employee.objects.create(
            employee_number="EMP-OTHER-UPD",
            legal_name="Other Update Employee",
            email="other-update@example.com",
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 10, 1),
            created_by=self.comptroller,
        )
        other_plan = self.make_plan(
            employee=other,
            effective_date=date(2026, 10, 1),
        )
        self.expect_database_rejection(
            lambda: EmployeePayrollRecord.objects.filter(
                pk=payroll.pk
            ).update(compensation_plan=other_plan)
        )
        payroll.refresh_from_db()
        self.assertEqual(
            payroll.compensation_plan_id,
            self.compensation_plan.pk,
        )

    def test_direct_insert_rejects_reversed_period(self):
        self.expect_database_rejection(
            lambda: self.make_payroll(
                start=date(2026, 10, 20),
                end=date(2026, 10, 10),
            )
        )
