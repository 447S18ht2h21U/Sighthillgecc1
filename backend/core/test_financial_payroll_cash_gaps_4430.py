"""Disposable database regression for Step 4430."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import test_employee_payroll as existing
from .employee_payroll_services import (
    approve_employee_payroll_record,
    create_employee_payroll_record,
    issue_employee_payroll_payment,
    mark_employee_payroll_paid,
)
from .financial_cash_exceptions_4428 import (
    preview_cash_exceptions_4428,
)
from .financial_payroll_cash_gaps_4430 import (
    issuance_gap_4430,
    missing_paid_date_gap_4430,
    preview_payroll_cash_gaps_4430,
)
from .models import EmployeePayrollRecord


class PayrollGapPopulated4430Tests(TestCase):
    setUp = existing.EmployeePayrollTests.setUp

    def make_payroll(self):
        return create_employee_payroll_record(
            self.comptroller,
            self.employee,
            self.compensation_plan,
            EmployeePayrollRecord.Kind.SALARY,
            date(2026, 10, 1),
            date(2026, 10, 15),
            Decimal("2500.00"),
            Decimal("500.00"),
            Decimal("2000.00"),
            {"source": "4430_ISOLATED_TEST"},
        )

    def approve(self, record):
        approve_employee_payroll_record(self.ceo, record.pk)

    def issue(self, record):
        return issue_employee_payroll_payment(
            self.ceo,
            record.pk,
            Decimal("2000.00"),
            "ACH",
            "4430-SYNTHETIC-ISSUANCE",
        )

    def test_01_issued_but_not_paid_listed(self):
        record = self.make_payroll()
        self.approve(record)
        self.issue(record)

        day = timezone.localdate()
        result = preview_payroll_cash_gaps_4430(day, day)

        self.assertEqual(result["exception_count"], 1)
        item = result["exceptions"][0]
        self.assertEqual(item["kind"], "EMPLOYEE_ISSUED_NOT_PAID")
        self.assertEqual(item["amount"], "2000.00")
        self.assertFalse(item["cash_settlement_verified"])
        self.assertEqual(
            item["review_date_type"],
            "ISSUANCE_DATE_NOT_SETTLEMENT",
        )

    def test_02_approved_but_not_issued_not_mislabeled(self):
        record = self.make_payroll()
        self.approve(record)

        day = timezone.localdate()
        result = preview_payroll_cash_gaps_4430(day, day)
        self.assertEqual(result["exception_count"], 0)
        self.assertFalse(result["cash_flow_complete"])

    def test_03_paid_transfers_to_existing_exception_category(self):
        record = self.make_payroll()
        self.approve(record)
        self.issue(record)

        mark_employee_payroll_paid(self.comptroller, record.pk)
        day = timezone.localdate()

        supplement = preview_payroll_cash_gaps_4430(day, day)
        original = preview_cash_exceptions_4428(day, day)

        self.assertEqual(supplement["exception_count"], 0)
        self.assertEqual(original["exception_count"], 1)
        self.assertEqual(
            original["exceptions"][0]["kind"],
            "EMPLOYEE_PAYROLL_SETTLEMENT",
        )
        self.assertFalse(
            original["exceptions"][0]["cash_settlement_verified"]
        )

    def test_04_issuance_review_date_boundary(self):
        record = self.make_payroll()
        self.approve(record)
        self.issue(record)

        tomorrow = timezone.localdate() + timedelta(days=1)
        result = preview_payroll_cash_gaps_4430(
            tomorrow, tomorrow
        )
        self.assertEqual(result["exception_count"], 0)

    def test_05_empty_database_access_read_only(self):
        day = timezone.localdate()

        with CaptureQueriesContext(connection) as captured:
            result = preview_payroll_cash_gaps_4430(day, day)

        self.assertEqual(result["exception_count"], 0)
        self.assertFalse(result["financial_statement_certified"])
        self.assertGreater(len(captured), 0)

        for query in captured:
            self.assertTrue(
                query["sql"].lstrip().upper().startswith("SELECT"),
                query["sql"],
            )


class PayrollGapDecision4430Tests(SimpleTestCase):
    def test_06_missing_timestamp_never_claims_cash_settlement(self):
        record = SimpleNamespace(
            pk="TEST-MISSING-DATE",
            status="PAID",
            paid_at=None,
            net_amount=Decimal("2000.00"),
        )
        result = missing_paid_date_gap_4430(record)
        self.assertEqual(
            result["kind"], "EMPLOYEE_PAID_WITHOUT_TIMESTAMP"
        )
        self.assertIsNone(result["review_date"])
        self.assertFalse(result["cash_settlement_verified"])
