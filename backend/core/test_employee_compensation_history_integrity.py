"""Database regression tests for approved employee compensation history.

Tests use Django's isolated test database with migrations 0068 and 0069.
"""

from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from . import test_employee_payroll as payroll_fixtures
from .models import EmployeeCompensationPlan


class EmployeeCompensationHistoryIntegrityTests(TestCase):
    def setUp(self):
        payroll_fixtures.EmployeePayrollTests.setUp(self)

    def create_plan(self, version, effective_date, status="APPROVED"):
        return EmployeeCompensationPlan.objects.create(
            employee=self.employee,
            version=version,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            status=status,
            effective_date=effective_date,
            compensation_terms={"annual_salary": "65000.00"},
            created_by=self.comptroller,
            approved_by=(
                self.comptroller if status == "APPROVED" else None
            ),
        )

    def assert_database_rejects(self, action):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                action()

    def test_approved_plan_cannot_be_deleted(self):
        plan_id = self.compensation_plan.pk

        self.assert_database_rejects(
            lambda: EmployeeCompensationPlan.objects.filter(
                pk=plan_id
            ).delete()
        )

        self.assertTrue(
            EmployeeCompensationPlan.objects.filter(pk=plan_id).exists()
        )

    def test_approved_plan_cannot_be_modified(self):
        self.assert_database_rejects(
            lambda: EmployeeCompensationPlan.objects.filter(
                pk=self.compensation_plan.pk
            ).update(compensation_terms={"annual_salary": "99000.00"})
        )

    def test_duplicate_approved_effective_date_rejected(self):
        self.assert_database_rejects(
            lambda: self.create_plan(
                version=2,
                effective_date=date(2026, 10, 1),
            )
        )

    def test_draft_cannot_be_approved_with_duplicate_date(self):
        draft = self.create_plan(
            version=2,
            effective_date=date(2026, 10, 1),
            status="DRAFT",
        )

        self.assert_database_rejects(
            lambda: EmployeeCompensationPlan.objects.filter(
                pk=draft.pk
            ).update(status="APPROVED")
        )

        draft.refresh_from_db()
        self.assertEqual(draft.status, "DRAFT")

    def test_new_approved_version_on_later_date_allowed(self):
        later = self.create_plan(
            version=2,
            effective_date=date(2026, 11, 1),
        )

        self.assertEqual(later.status, "APPROVED")
        self.assertTrue(
            EmployeeCompensationPlan.objects.filter(
                pk=self.compensation_plan.pk,
                status="APPROVED",
            ).exists()
        )

    def test_draft_with_shared_date_remains_allowed(self):
        draft = self.create_plan(
            version=2,
            effective_date=date(2026, 10, 1),
            status="DRAFT",
        )

        self.assertEqual(draft.status, "DRAFT")
        self.assertEqual(
            draft.effective_date,
            self.compensation_plan.effective_date,
        )
