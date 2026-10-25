from datetime import date
from decimal import Decimal
from unittest import skipUnless

from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from .employee_payroll_services import (
    approve_employee_payroll_record,
    create_employee_payroll_record,
)
from .models import EmployeeCompensationPlan, EmployeePayrollRecord
from . import test_employee_payroll as payroll_test_setup


@skipUnless(connection.vendor == "postgresql", "PostgreSQL only")
class PostgreSQLPayrollIntegrityTests(TestCase):

    def setUp(self):
        payroll_test_setup.EmployeePayrollTests.setUp(self)

    def create_approved_payroll(self):
        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal("2500.00"),
            Decimal("500.00"),
            Decimal("2000.00"),
            {"source": "SALARY_PLAN"},
        )
        approve_employee_payroll_record(self.ceo, record.id)
        return record

    def test_approved_payroll_amount_is_immutable(self):
        record = self.create_approved_payroll()

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=record.id
                ).update(net_amount=Decimal("9999.00"))

        record.refresh_from_db()
        self.assertEqual(record.net_amount, Decimal("2000.00"))

    def test_approved_compensation_plan_is_immutable(self):
        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeeCompensationPlan.objects.filter(
                    pk=self.compensation_plan.id
                ).update(
                    compensation_terms={"annual_salary": "99999.00"}
                )

        self.compensation_plan.refresh_from_db()
        self.assertEqual(
            self.compensation_plan.compensation_terms["annual_salary"],
            "60000.00",
        )

    def test_approved_payroll_cannot_acquire_payment_timestamp(self):
        record = self.create_approved_payroll()

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=record.id
                ).update(paid_at=timezone.now())

        record.refresh_from_db()
        self.assertIsNone(record.paid_at)
        self.assertEqual(
            record.status,
            EmployeePayrollRecord.Status.APPROVED,
        )

    def test_approval_cannot_change_financial_amount(self):
        record = create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal("2500.00"),
            Decimal("500.00"),
            Decimal("2000.00"),
            {"source": "SALARY_PLAN"},
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=record.id
                ).update(
                    status=EmployeePayrollRecord.Status.APPROVED,
                    approved_by=self.ceo,
                    approved_at=timezone.now(),
                    net_amount=Decimal("9999.00"),
                )

        record.refresh_from_db()
        self.assertEqual(record.status, EmployeePayrollRecord.Status.DRAFT)
        self.assertEqual(record.net_amount, Decimal("2000.00"))

    def test_approved_payroll_cannot_return_to_draft(self):
        record = self.create_approved_payroll()

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                EmployeePayrollRecord.objects.filter(
                    pk=record.id
                ).update(status=EmployeePayrollRecord.Status.DRAFT)

        record.refresh_from_db()
        self.assertEqual(record.status, EmployeePayrollRecord.Status.APPROVED)

    def test_legitimate_approval_and_settlement(self):
        from .employee_payroll_services import (
            issue_employee_payroll_payment,
            mark_employee_payroll_paid,
        )

        record = self.create_approved_payroll()
        record.refresh_from_db()

        self.assertEqual(
            record.status,
            EmployeePayrollRecord.Status.APPROVED,
        )
        self.assertEqual(record.approved_by_id, self.ceo.id)
        self.assertIsNotNone(record.approved_at)
        self.assertIsNone(record.paid_at)

        issue_employee_payroll_payment(
            self.ceo,
            record.id,
            Decimal("2000.00"),
            "ACH",
            "PAYROLL-PG-INTEGRITY-001",
        )

        mark_employee_payroll_paid(self.comptroller, record.id)
        record.refresh_from_db()

        self.assertEqual(
            record.status,
            EmployeePayrollRecord.Status.PAID,
        )
        self.assertEqual(record.net_amount, Decimal("2000.00"))
        self.assertEqual(record.approved_by_id, self.ceo.id)
        self.assertIsNotNone(record.approved_at)
        self.assertIsNotNone(record.paid_at)
