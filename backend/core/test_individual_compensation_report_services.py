"""Isolation and read-only tests for individual compensation reports."""

from datetime import date

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from django.utils import timezone
from .models import ContractorPaymentRecord, EmployeePayrollRecord, Role, User
from .employee_payroll_services import (
    approve_employee_payroll_record,
    issue_employee_payroll_payment,
    mark_employee_payroll_paid,
)
from .contractor_payment_services import (
    approve_contractor_payment_record,
    mark_contractor_payment_paid,
)
from .contractor_payment_issuance_services import issue_contractor_payment
from .contractor_payment_settlement_services import (
    verify_contractor_payment_settlement,
)
from .test_access_compensation_scope import CompensationOwnershipScopeTests
from .individual_compensation_report_services import (
    own_individual_compensation_period_report,
)


class IndividualCompensationReportSecurityTests(TestCase):
    make_employee = CompensationOwnershipScopeTests.make_employee
    make_contractor = CompensationOwnershipScopeTests.make_contractor
    make_employee_record = CompensationOwnershipScopeTests.make_employee_record
    make_contractor_record = CompensationOwnershipScopeTests.make_contractor_record
    """Test reports using existing ownership fixture setup only."""

    def setUp(self):
        CompensationOwnershipScopeTests.setUp(self)
        self.ceo = User.objects.create_user(
            username="individual_report_test_ceo",
            role=Role.CEO,
            initials="IR",
        )

    def report(self, actor=None, start="2026-10-01", end="2026-10-31"):
        return own_individual_compensation_period_report(
            self.user_a if actor is None else actor,
            start,
            end,
        )

    def approve_owned(self):
        approve_employee_payroll_record(
            self.ceo, self.employee_record_a.pk
        )
        approve_contractor_payment_record(
            self.ceo, self.contractor_record_a.pk
        )

    def pay_owned(self):
        self.approve_owned()

        issue_employee_payroll_payment(
            self.ceo,
            self.employee_record_a.pk,
            self.employee_record_a.net_amount,
            "ACH",
            f"INDIVIDUAL-EMP-{self.employee_record_a.pk}",
        )
        mark_employee_payroll_paid(
            self.admin, self.employee_record_a.pk
        )

        issue_contractor_payment(
            self.ceo,
            self.contractor_record_a.pk,
            self.contractor_record_a.final_amount,
            "ACH",
            f"INDIVIDUAL-CTR-{self.contractor_record_a.pk}",
            "Individual report test payment issuance",
        )
        verify_contractor_payment_settlement(
            self.admin,
            self.contractor_record_a.pk,
            timezone.localdate(),
            self.contractor_record_a.final_amount,
            f"INDIVIDUAL-BANK-{self.contractor_record_a.pk}",
        )
        mark_contractor_payment_paid(
            self.admin, self.contractor_record_a.pk
        )

    def test_draft_records_are_excluded(self):
        report = self.report()

        self.assertEqual(report["employee_records"], [])
        self.assertEqual(report["contractor_records"], [])

    def test_approved_owned_records_are_included(self):
        self.approve_owned()
        report = self.report()

        self.assertEqual(
            {row["record_id"] for row in report["employee_records"]},
            {str(self.employee_record_a.pk)},
        )
        self.assertEqual(
            {row["record_id"] for row in report["contractor_records"]},
            {str(self.contractor_record_a.pk)},
        )

    def test_other_users_compensation_is_excluded(self):
        self.approve_owned()

        approve_employee_payroll_record(
            self.ceo, self.employee_record_b.pk
        )
        approve_contractor_payment_record(
            self.ceo, self.contractor_record_b.pk
        )

        report = self.report()

        self.assertNotIn(
            str(self.employee_record_b.pk),
            {row["record_id"] for row in report["employee_records"]},
        )
        self.assertNotIn(
            str(self.contractor_record_b.pk),
            {row["record_id"] for row in report["contractor_records"]},
        )

    def test_approved_records_are_not_labeled_paid(self):
        self.approve_owned()
        report = self.report()

        for row in (
            report["employee_records"] + report["contractor_records"]
        ):
            self.assertEqual(row["status"], "APPROVED")
            self.assertEqual(
                row["status_label"], "Approved - Not Yet Paid"
            )

    def test_paid_status_is_labeled_paid(self):
        self.pay_owned()

        report = self.report()

        for row in (
            report["employee_records"] + report["contractor_records"]
        ):
            self.assertEqual(row["status_label"], "Paid")

    def test_overlap_includes_full_obligation(self):
        self.approve_owned()

        report = self.report(
            start="2026-10-10",
            end="2026-10-12",
        )

        self.assertEqual(
            report["amount_basis"],
            "full_obligation_not_prorated",
        )
        self.assertEqual(len(report["employee_records"]), 1)
        self.assertEqual(len(report["contractor_records"]), 1)

    def test_non_overlapping_dates_exclude_records(self):
        self.approve_owned()

        report = self.report(
            start="2026-11-01",
            end="2026-11-30",
        )

        self.assertEqual(report["employee_records"], [])
        self.assertEqual(report["contractor_records"], [])

    def test_unlinked_account_sees_no_compensation(self):
        self.approve_owned()
        report = self.report(actor=self.unlinked)

        self.assertEqual(report["employee_records"], [])
        self.assertEqual(report["contractor_records"], [])

    def test_inactive_account_sees_no_compensation(self):
        self.approve_owned()

        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        report = self.report(actor=self.user_a)

        self.assertEqual(report["employee_records"], [])
        self.assertEqual(report["contractor_records"], [])

    def test_report_does_not_modify_financial_records(self):
        self.approve_owned()

        before_employee = list(
            EmployeePayrollRecord.objects.values_list("pk", "status")
        )
        before_contractor = list(
            ContractorPaymentRecord.objects.values_list("pk", "status")
        )

        self.report()

        self.assertEqual(
            before_employee,
            list(EmployeePayrollRecord.objects.values_list("pk", "status")),
        )
        self.assertEqual(
            before_contractor,
            list(ContractorPaymentRecord.objects.values_list("pk", "status")),
        )