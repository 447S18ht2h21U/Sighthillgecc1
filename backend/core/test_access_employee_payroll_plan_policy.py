"""Regression tests for nonbinding employee payroll-plan safeguards."""

from datetime import date, datetime

from django.test import SimpleTestCase

from .access_employee_payroll_plan_policy import (
    employee_compensation_policy_grants_access,
    validate_compensation_approval_separation,
    validate_payroll_plan,
)


class EmployeePayrollPlanPolicyTests(SimpleTestCase):

    def valid_plan(self, **overrides):
        values = {
            "employee_id": 101,
            "plan_employee_id": 101,
            "plan_status": "APPROVED",
            "plan_effective_date": date(2026, 1, 1),
            "period_start": date(2026, 3, 1),
            "period_end": date(2026, 3, 15),
            "next_approved_effective_date": None,
        }
        values.update(overrides)
        return validate_payroll_plan(**values)

    def test_valid_approved_plan_for_correct_employee(self):
        self.assertTrue(self.valid_plan())

    def test_different_employee_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            self.valid_plan(plan_employee_id=202)

    def test_missing_employee_identity_is_rejected(self):
        for changes in (
            {"employee_id": None},
            {"plan_employee_id": None},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.valid_plan(**changes)

    def test_unapproved_plan_is_rejected(self):
        for status in ("DRAFT", "SUPERSEDED", ""):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    self.valid_plan(plan_status=status)

    def test_future_plan_cannot_apply_to_earlier_period(self):
        with self.assertRaises(ValueError):
            self.valid_plan(
                plan_effective_date=date(2026, 4, 1)
            )

    def test_reversed_or_invalid_period_is_rejected(self):
        invalid_cases = (
            {"period_start": date(2026, 4, 1),
             "period_end": date(2026, 3, 1)},
            {"period_start": "2026-03-01"},
            {"period_end": datetime(2026, 3, 15)},
        )
        for changes in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.valid_plan(**changes)

    def test_mid_period_rate_change_requires_split(self):
        with self.assertRaises(ValueError):
            self.valid_plan(
                next_approved_effective_date=date(2026, 3, 10)
            )

    def test_new_rate_effective_at_period_start_replaces_old(self):
        with self.assertRaises(ValueError):
            self.valid_plan(
                next_approved_effective_date=date(2026, 3, 1)
            )

    def test_period_ending_before_rate_change_is_valid(self):
        self.assertTrue(
            self.valid_plan(
                next_approved_effective_date=date(2026, 3, 16)
            )
        )

    def test_conflicting_or_invalid_next_date_is_rejected(self):
        for next_date in (
            date(2026, 1, 1),
            date(2025, 12, 31),
            "2026-04-01",
        ):
            with self.subTest(next_date=next_date):
                with self.assertRaises(ValueError):
                    self.valid_plan(
                        next_approved_effective_date=next_date
                    )

    def test_employee_and_requester_self_approval_rejected(self):
        for approver, employee, requester in (
            (10, 10, 20),
            (10, 20, 10),
        ):
            with self.subTest(
                approver=approver,
                employee=employee,
                requester=requester,
            ):
                with self.assertRaises(ValueError):
                    validate_compensation_approval_separation(
                        approver, employee, requester
                    )

    def test_distinct_approver_requester_and_employee_allowed(self):
        self.assertTrue(
            validate_compensation_approval_separation(
                approver_user_id=10,
                employee_user_id=20,
                requester_user_id=30,
            )
        )

    def test_missing_requester_or_approver_is_rejected(self):
        for approver, requester in ((None, 30), (10, None)):
            with self.subTest(
                approver=approver,
                requester=requester,
            ):
                with self.assertRaises(ValueError):
                    validate_compensation_approval_separation(
                        approver, 20, requester
                    )

    def test_unlinked_employee_still_requires_independent_approval(self):
        self.assertTrue(
            validate_compensation_approval_separation(
                approver_user_id=10,
                employee_user_id=None,
                requester_user_id=30,
            )
        )
        with self.assertRaises(ValueError):
            validate_compensation_approval_separation(
                approver_user_id=10,
                employee_user_id=None,
                requester_user_id=10,
            )

    def test_policy_never_grants_live_access(self):
        self.assertFalse(
            employee_compensation_policy_grants_access()
        )
