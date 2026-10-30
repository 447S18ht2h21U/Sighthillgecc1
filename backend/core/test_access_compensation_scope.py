"""Isolation tests for employee and contractor self-service pay visibility."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import AnonymousUser

from .access_compensation_scope import (
    own_employee_payroll_scope,
    own_contractor_payment_scope,
)
from .models import (
    Contractor,
    ContractorCompensationPlan,
    ContractorEngagement,
    ContractorPaymentRecord,
    Employee,
    EmployeeCompensationPlan,
    EmployeePayrollRecord,
    Role,
    User,
)


class CompensationOwnershipScopeTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="scope_admin",
            role=Role.COMPTROLLER,
            initials="SA",
        )
        self.user_a = User.objects.create_user(
            username="scope_user_a",
            role=Role.SALES_ASSOCIATE,
            initials="AA",
        )
        self.user_b = User.objects.create_user(
            username="scope_user_b",
            role=Role.TECHNICIAN,
            initials="BB",
        )
        self.unlinked = User.objects.create_user(
            username="scope_unlinked",
            role=Role.CEO,
            initials="UU",
        )

        self.employee_a = self.make_employee("A", self.user_a)
        self.employee_b = self.make_employee("B", self.user_b)
        self.contractor_a = self.make_contractor("A", self.user_a)
        self.contractor_b = self.make_contractor("B", self.user_b)

        self.employee_record_a = self.make_employee_record(self.employee_a)
        self.employee_record_b = self.make_employee_record(self.employee_b)
        self.contractor_record_a = self.make_contractor_record(self.contractor_a)
        self.contractor_record_b = self.make_contractor_record(self.contractor_b)

    def make_employee(self, suffix, user):
        return Employee.objects.create(
            employee_number=f"SCOPE-EMP-{suffix}",
            legal_name=f"Scope Employee {suffix}",
            email="shared@example.com",
            user=user,
            status=Employee.Status.ACTIVE,
            hire_date=date(2026, 10, 1),
            created_by=self.admin,
        )

    def make_contractor(self, suffix, user):
        return Contractor.objects.create(
            contractor_number=f"SCOPE-CTR-{suffix}",
            legal_name=f"Scope Contractor {suffix}",
            email="shared@example.com",
            user=user,
            created_by=self.admin,
        )

    def make_employee_record(self, employee):
        plan = EmployeeCompensationPlan.objects.create(
            employee=employee,
            version=1,
            kind=EmployeeCompensationPlan.Kind.SALARY,
            effective_date=date(2026, 10, 1),
            compensation_terms={"annual_salary": "60000.00"},
            status=EmployeeCompensationPlan.Status.APPROVED,
            created_by=self.admin,
            approved_by=self.admin,
        )
        return EmployeePayrollRecord.objects.create(
            employee=employee,
            compensation_plan=plan,
            kind=EmployeePayrollRecord.Kind.SALARY,
            status=EmployeePayrollRecord.Status.DRAFT,
            payroll_period_start=date(2026, 10, 1),
            payroll_period_end=date(2026, 10, 15),
            gross_amount=Decimal("2500.00"),
            deduction_amount=Decimal("500.00"),
            net_amount=Decimal("2000.00"),
            calculation_snapshot={"source": "PRIVACY_TEST"},
            created_by=self.admin,
        )

    def make_contractor_record(self, contractor):
        engagement = ContractorEngagement.objects.create(
            contractor=contractor,
            engagement_code=f"ENG-{contractor.contractor_number}",
            role_description="Test Contractor",
            start_date=date(2026, 10, 1),
            status=ContractorEngagement.Status.ACTIVE,
            created_by=self.admin,
        )
        plan = ContractorCompensationPlan.objects.create(
            engagement=engagement,
            version=1,
            effective_date=date(2026, 10, 1),
            compensation_terms={"amount": "500.00"},
            status=ContractorCompensationPlan.Status.APPROVED,
            created_by=self.admin,
            approved_by=self.admin,
        )
        return ContractorPaymentRecord.objects.create(
            engagement=engagement,
            compensation_plan=plan,
            kind=ContractorPaymentRecord.Kind.FIXED_COMPENSATION,
            status=ContractorPaymentRecord.Status.DRAFT,
            payment_period_start=date(2026, 10, 1),
            payment_period_end=date(2026, 10, 15),
            basis_amount=Decimal("500.00"),
            deduction_amount=Decimal("0.00"),
            final_amount=Decimal("500.00"),
            calculation_snapshot={"source": "PRIVACY_TEST"},
            created_by=self.admin,
        )

    def test_each_employee_sees_only_own_payroll(self):
        self.assertEqual(
            set(own_employee_payroll_scope(self.user_a).values_list("pk", flat=True)),
            {self.employee_record_a.pk},
        )
        self.assertEqual(
            set(own_employee_payroll_scope(self.user_b).values_list("pk", flat=True)),
            {self.employee_record_b.pk},
        )

    def test_each_contractor_sees_only_own_payments(self):
        self.assertEqual(
            set(own_contractor_payment_scope(self.user_a).values_list("pk", flat=True)),
            {self.contractor_record_a.pk},
        )
        self.assertEqual(
            set(own_contractor_payment_scope(self.user_b).values_list("pk", flat=True)),
            {self.contractor_record_b.pk},
        )

    def test_unlinked_account_cannot_see_other_compensation(self):
        self.assertFalse(own_employee_payroll_scope(self.unlinked).exists())
        self.assertFalse(own_contractor_payment_scope(self.unlinked).exists())

    def test_inactive_account_cannot_see_compensation(self):
        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        self.assertFalse(own_employee_payroll_scope(self.user_a).exists())
        self.assertFalse(own_contractor_payment_scope(self.user_a).exists())

    def test_anonymous_and_missing_users_are_denied(self):
        for actor in (None, AnonymousUser()):
            with self.subTest(actor=str(type(actor))):
                self.assertFalse(own_employee_payroll_scope(actor).exists())
                self.assertFalse(own_contractor_payment_scope(actor).exists())

    def test_dual_linked_user_sees_only_both_owned_record_types(self):
        self.assertEqual(own_employee_payroll_scope(self.user_a).count(), 1)
        self.assertEqual(own_contractor_payment_scope(self.user_a).count(), 1)
        self.assertNotIn(
            self.employee_record_b.pk,
            own_employee_payroll_scope(self.user_a).values_list("pk", flat=True),
        )
        self.assertNotIn(
            self.contractor_record_b.pk,
            own_contractor_payment_scope(self.user_a).values_list("pk", flat=True),
        )

    def test_role_does_not_override_compensation_ownership(self):
        self.user_a.role = Role.CEO
        self.user_a.save(update_fields=["role"])

        self.assertEqual(
            set(own_employee_payroll_scope(self.user_a).values_list("pk", flat=True)),
            {self.employee_record_a.pk},
        )
        self.assertEqual(
            set(own_contractor_payment_scope(self.user_a).values_list("pk", flat=True)),
            {self.contractor_record_a.pk},
        )
