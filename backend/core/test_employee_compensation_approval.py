"""Independent, audited employee compensation approval tests.

Execute against Django's isolated test database only.
"""

from datetime import date
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .employee_compensation_services import approve_employee_compensation_plan
from .models import (
    AuditEvent,
    AuditHead,
    Employee,
    EmployeeCompensationPlan,
    EmployeePayrollRecord,
    Outbox,
    Role,
    User,
)


class EmployeeCompensationApprovalTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="comp_approval_comptroller",
            password="TestPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.requester = User.objects.create_user(
            username="comp_approval_requester",
            password="TestPassword2026!",
            role=Role.SALES_MANAGER,
        )
        self.ceo = User.objects.create_user(
            username="comp_approval_ceo",
            password="TestPassword2026!",
            role=Role.CEO,
        )
        self.employee_user = User.objects.create_user(
            username="comp_approval_employee",
            password="TestPassword2026!",
            role=Role.SALES_ASSOCIATE,
        )
        self.employee = Employee.objects.create(
            employee_number="EMP-COMP-APPROVAL",
            legal_name="Compensation Approval Test Employee",
            email="comp-approval@example.com",
            user=self.employee_user,
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 1, 1),
            created_by=self.comptroller,
        )

    def plan(self, creator=None, effective=None, version=1):
        return EmployeeCompensationPlan.objects.create(
            employee=self.employee,
            version=version,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            status=EmployeeCompensationPlan.Status.DRAFT,
            effective_date=effective or date(2026, 10, 1),
            compensation_terms={"annual_salary": "60000.00"},
            created_by=creator or self.requester,
        )

    def approve(self, actor, plan, reason="Approved salary terms"):
        return approve_employee_compensation_plan(
            actor, plan.pk, reason=reason
        )

    def test_independent_comptroller_can_approve_and_audit(self):
        plan = self.plan()
        self.approve(self.comptroller, plan)
        plan.refresh_from_db()

        self.assertEqual(plan.status, "APPROVED")
        self.assertEqual(plan.approved_by_id, self.comptroller.pk)
        self.assertIsNotNone(plan.approved_at)

        event = AuditEvent.objects.get(
            action="employee.compensation.approved",
            entity_id=plan.pk,
        )
        self.assertEqual(event.actor_id, self.comptroller.pk)
        self.assertEqual(event.payload["reason"], "Approved salary terms")
        self.assertTrue(Outbox.objects.filter(event=event).exists())
        call_command("verify_audit")

    def test_sales_manager_cannot_approve(self):
        plan = self.plan()
        with self.assertRaises(PermissionDenied):
            self.approve(self.requester, plan)

    def test_ceo_cannot_approve_without_comptroller_authority(self):
        plan = self.plan()
        with self.assertRaises(PermissionDenied):
            self.approve(self.ceo, plan)

    def test_stale_actor_role_is_rechecked(self):
        plan = self.plan()
        self.comptroller.role = Role.CEO
        self.comptroller.save(update_fields=["role"])
        with self.assertRaises(PermissionDenied):
            self.approve(
                User(pk=self.comptroller.pk, role=Role.COMPTROLLER),
                plan,
            )

    def test_disabled_comptroller_cannot_approve(self):
        plan = self.plan()
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.approve(self.comptroller, plan)

    def test_requester_cannot_approve_own_request(self):
        plan = self.plan(creator=self.comptroller)
        with self.assertRaises((PermissionDenied, ValidationError)):
            self.approve(self.comptroller, plan)

    def test_employee_cannot_approve_own_compensation(self):
        self.employee.user = self.comptroller
        self.employee.save(update_fields=["user"])
        plan = self.plan()
        with self.assertRaises((PermissionDenied, ValidationError)):
            self.approve(self.comptroller, plan)

    def test_approval_requires_written_reason(self):
        plan = self.plan()
        with self.assertRaises(ValidationError):
            self.approve(self.comptroller, plan, reason="   ")

    def test_only_draft_plans_can_be_approved(self):
        plan = self.plan()
        self.approve(self.comptroller, plan)
        with self.assertRaises(ValidationError):
            self.approve(self.comptroller, plan)

    def test_missing_compensation_terms_rejected(self):
        plan = self.plan()
        plan.compensation_terms = {}
        plan.save(update_fields=["compensation_terms"])
        with self.assertRaises(ValidationError):
            self.approve(self.comptroller, plan)

    def test_inactive_employee_rejected(self):
        plan = self.plan()
        self.employee.status = Employee.Status.INACTIVE
        self.employee.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            self.approve(self.comptroller, plan)

    def test_earlier_approved_payroll_blocks_retroactive_change(self):
        original = self.plan(effective=date(2026, 1, 1))
        self.approve(self.comptroller, original)

        record = EmployeePayrollRecord.objects.create(
            employee=self.employee,
            compensation_plan=original,
            kind=EmployeePayrollRecord.Kind.SALARY,
            payroll_period_start=date(2026, 3, 1),
            payroll_period_end=date(2026, 3, 31),
            gross_amount="1000.00",
            deduction_amount="100.00",
            net_amount="900.00",
            calculation_snapshot={"test": True},
            created_by=self.comptroller,
        )
        from .employee_payroll_services import approve_employee_payroll_record
        approve_employee_payroll_record(self.ceo, record.pk)

        backdated = self.plan(
            effective=date(2026, 3, 15),
            version=2,
        )
        with self.assertRaises(ValidationError):
            self.approve(self.comptroller, backdated)

    def test_audit_failure_rolls_back_approval(self):
        plan = self.plan()
        before = (
            AuditHead.objects.get(pk=1).sequence,
            AuditEvent.objects.count(),
            Outbox.objects.count(),
        )

        with patch(
            "core.employee_compensation_services.audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated audit failure"
            ):
                self.approve(self.comptroller, plan)

        plan.refresh_from_db()
        self.assertEqual(plan.status, "DRAFT")
        self.assertIsNone(plan.approved_by_id)
        self.assertIsNone(plan.approved_at)
        self.assertEqual(
            (
                AuditHead.objects.get(pk=1).sequence,
                AuditEvent.objects.count(),
                Outbox.objects.count(),
            ),
            before,
        )
