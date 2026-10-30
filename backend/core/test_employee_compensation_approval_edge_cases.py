"""Additional safeguards for employee compensation approval."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .employee_compensation_services import approve_employee_compensation_plan
from .models import (
    AuditEvent,
    AuditHead,
    Employee,
    EmployeeCompensationPlan,
    Outbox,
    Role,
    User,
)


class EmployeeCompensationApprovalEdgeCaseTests(TestCase):
    def setUp(self):
        self.approver = User.objects.create_user(
            username="edge_comp_approver",
            password="TestOnly2026!",
            role=Role.COMPTROLLER,
        )
        self.requester = User.objects.create_user(
            username="edge_comp_requester",
            password="TestOnly2026!",
            role=Role.SALES_MANAGER,
        )
        self.employee = Employee.objects.create(
            employee_number="EMP-EDGE-APPROVAL",
            legal_name="Edge Case Test Employee",
            email="edge-employee@example.com",
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 1, 1),
            created_by=self.approver,
        )

    def make_plan(self, version, effective_date):
        return EmployeeCompensationPlan.objects.create(
            employee=self.employee,
            version=version,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            effective_date=effective_date,
            compensation_terms={"annual_salary": "60000.00"},
            created_by=self.requester,
        )

    def approve(self, plan):
        return approve_employee_compensation_plan(
            self.approver,
            plan.pk,
            reason="Reviewed and independently approved",
        )

    def test_outbox_failure_rolls_back_approval_and_audit(self):
        plan = self.make_plan(1, date(2026, 10, 1))
        before = (
            AuditHead.objects.get(pk=1).sequence,
            AuditHead.objects.get(pk=1).digest,
            AuditEvent.objects.count(),
            Outbox.objects.count(),
        )

        with patch.object(
            Outbox.objects,
            "create",
            side_effect=RuntimeError("Simulated outbox failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated outbox failure"
            ):
                self.approve(plan)

        plan.refresh_from_db()
        self.assertEqual(plan.status, EmployeeCompensationPlan.Status.DRAFT)
        self.assertIsNone(plan.approved_by_id)
        self.assertIsNone(plan.approved_at)

        after = (
            AuditHead.objects.get(pk=1).sequence,
            AuditHead.objects.get(pk=1).digest,
            AuditEvent.objects.count(),
            Outbox.objects.count(),
        )
        self.assertEqual(after, before)

    def test_later_version_preserves_original_approved_terms(self):
        first = self.make_plan(1, date(2026, 1, 1))
        self.approve(first)
        first.refresh_from_db()

        original = (
            first.version,
            first.kind,
            first.effective_date,
            first.compensation_terms.copy(),
            first.approved_at,
            first.approved_by_id,
        )

        second = self.make_plan(2, date(2026, 11, 1))
        second.compensation_terms = {"annual_salary": "66000.00"}
        second.save(update_fields=["compensation_terms"])
        self.approve(second)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(first.status, EmployeeCompensationPlan.Status.APPROVED)
        self.assertEqual(second.status, EmployeeCompensationPlan.Status.APPROVED)
        self.assertEqual(
            (
                first.version,
                first.kind,
                first.effective_date,
                first.compensation_terms,
                first.approved_at,
                first.approved_by_id,
            ),
            original,
        )
        self.assertEqual(
            second.compensation_terms,
            {"annual_salary": "66000.00"},
        )

    def test_duplicate_approved_effective_date_is_rejected(self):
        first = self.make_plan(1, date(2026, 10, 1))
        self.approve(first)

        second = self.make_plan(2, date(2026, 10, 1))
        with self.assertRaises(ValidationError):
            self.approve(second)

        second.refresh_from_db()
        self.assertEqual(second.status, EmployeeCompensationPlan.Status.DRAFT)
        self.assertIsNone(second.approved_by_id)
