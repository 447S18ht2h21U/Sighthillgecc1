"""Regression tests for payroll-to-compensation-plan integration.

These tests intentionally describe safeguards not yet connected to
the employee payroll creation service. They should fail until the
service implements the protections. Test data is isolated.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from . import test_employee_payroll as existing_payroll_tests
from .employee_payroll_services import create_employee_payroll_record
from .models import Employee, EmployeeCompensationPlan


class EmployeePayrollPlanIntegrationTests(TestCase):

    def setUp(self):
        existing_payroll_tests.EmployeePayrollTests.setUp(self)

    def create_payroll(self, plan, start, end):
        return create_employee_payroll_record(
            self.comptroller,
            self.employee,
            plan,
            EmployeeCompensationPlan.Kind.SALARY,
            start,
            end,
            Decimal("2500.00"),
            Decimal("500.00"),
            Decimal("2000.00"),
            {"source": "INTEGRATION_REGRESSION_TEST"},
        )

    def create_new_plan(self, version, effective_date, employee=None):
        return EmployeeCompensationPlan.objects.create(
            employee=employee or self.employee,
            version=version,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            effective_date=effective_date,
            compensation_terms={"annual_salary": "65000.00"},
            status=EmployeeCompensationPlan.Status.APPROVED,
            created_by=self.comptroller,
            approved_by=self.comptroller,
        )

    def test_rejects_plan_belonging_to_another_employee(self):
        other = Employee.objects.create(
            employee_number="EMP-INTEGRATION-OTHER",
            legal_name="Other Test Employee",
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 10, 1),
            created_by=self.comptroller,
        )
        other_plan = self.create_new_plan(
            version=1,
            effective_date=date(2026, 10, 1),
            employee=other,
        )
        with self.assertRaises(ValidationError):
            self.create_payroll(
                other_plan,
                date(2026, 10, 1),
                date(2026, 10, 15),
            )

    def test_rejects_plan_not_yet_effective(self):
        future = self.create_new_plan(
            version=2,
            effective_date=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError):
            self.create_payroll(
                future,
                date(2026, 10, 16),
                date(2026, 10, 31),
            )

    def test_rejects_old_plan_after_new_version_begins(self):
        self.create_new_plan(
            version=2,
            effective_date=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError):
            self.create_payroll(
                self.compensation_plan,
                date(2026, 11, 1),
                date(2026, 11, 15),
            )

    def test_rejects_period_spanning_new_version_date(self):
        self.create_new_plan(
            version=2,
            effective_date=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError):
            self.create_payroll(
                self.compensation_plan,
                date(2026, 10, 25),
                date(2026, 11, 10),
            )
