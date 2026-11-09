"""Populated and read-only regression for Step 4431."""

from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import test_employee_payroll as fixtures
from .employee_payroll_services import (
    create_employee_payroll_record,
    approve_employee_payroll_record,
    issue_employee_payroll_payment,
    mark_employee_payroll_paid,
)
from .financial_cash_inventory_4431 import (
    preview_cash_exception_inventory_4431,
)
from .models import EmployeePayrollRecord


class CashInventory4431Tests(TestCase):
    setUp = fixtures.EmployeePayrollTests.setUp

    def make_approved(self):
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
            {"source": "4431_TEST_ONLY"},
        )
        approve_employee_payroll_record(self.ceo, record.pk)
        return record

    def issue(self, record):
        return issue_employee_payroll_payment(
            self.ceo, record.pk, Decimal("2000.00"),
            "ACH", "4431-TEST-ISSUANCE"
        )

    def test_01_approved_unissued_payroll_visible(self):
        record = self.make_approved()
        result = preview_cash_exception_inventory_4431(
            date(2026, 10, 15), date(2026, 10, 15)
        )
        self.assertEqual(result["exception_count"], 1)
        self.assertEqual(
            result["exceptions"][0]["record_id"], str(record.pk)
        )
        self.assertEqual(
            result["exceptions"][0]["kind"],
            "EMPLOYEE_APPROVED_NOT_ISSUED"
        )
        self.assertFalse(result["bank_reconciled"])

    def test_02_issued_payroll_replaces_unissued_category(self):
        record = self.make_approved()
        self.issue(record)
        day = timezone.localdate()
        result = preview_cash_exception_inventory_4431(
            date(2026, 10, 15), day
        )
        kinds = [item["kind"] for item in result["exceptions"]]
        self.assertIn("EMPLOYEE_ISSUED_NOT_PAID", kinds)
        self.assertNotIn("EMPLOYEE_APPROVED_NOT_ISSUED", kinds)
        self.assertEqual(result["exception_count"], 1)

    def test_03_paid_payroll_remains_unsettled_exception(self):
        record = self.make_approved()
        self.issue(record)
        mark_employee_payroll_paid(self.comptroller, record.pk)
        result = preview_cash_exception_inventory_4431(
            date(2026, 10, 15), timezone.localdate()
        )
        kinds = [item["kind"] for item in result["exceptions"]]
        self.assertEqual(kinds, ["EMPLOYEE_PAYROLL_SETTLEMENT"])
        self.assertFalse(result["financial_statement_certified"])

    def test_04_empty_database_read_only(self):
        day = timezone.localdate()
        with CaptureQueriesContext(connection) as queries:
            result = preview_cash_exception_inventory_4431(day, day)
        self.assertEqual(result["exception_count"], 0)
        self.assertGreater(len(queries), 0)
        for query in queries:
            self.assertTrue(
                query["sql"].lstrip().upper().startswith("SELECT"),
                query["sql"],
            )
