"""Integration tests for ownership-safe individual compensation reports."""

from django.test import TestCase
from django.utils import timezone

from .models import Role, User
from .test_access_compensation_scope import CompensationOwnershipScopeTests
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
from .individual_compensation_report_with_evidence import (
    own_individual_compensation_report_with_evidence,
)


class IndividualCompensationReportEvidenceIntegrationTests(TestCase):
    """Reuse existing financial fixtures without inheriting extra tests."""

    make_employee = CompensationOwnershipScopeTests.make_employee
    make_contractor = CompensationOwnershipScopeTests.make_contractor
    make_employee_record = CompensationOwnershipScopeTests.make_employee_record
    make_contractor_record = CompensationOwnershipScopeTests.make_contractor_record

    def setUp(self):
        CompensationOwnershipScopeTests.setUp(self)
        self.ceo = User.objects.create_user(
            username="report_evidence_integration_ceo",
            role=Role.CEO,
            initials="RI",
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
            f"REPORT-EMP-{self.employee_record_a.pk}",
        )
        mark_employee_payroll_paid(
            self.admin, self.employee_record_a.pk
        )

        issue_contractor_payment(
            self.ceo,
            self.contractor_record_a.pk,
            self.contractor_record_a.final_amount,
            "ACH",
            f"REPORT-CTR-{self.contractor_record_a.pk}",
            "Isolated report integration test evidence",
        )
        verify_contractor_payment_settlement(
            self.admin,
            self.contractor_record_a.pk,
            timezone.localdate(),
            self.contractor_record_a.final_amount,
            f"REPORT-BANK-{self.contractor_record_a.pk}",
        )
        mark_contractor_payment_paid(
            self.admin, self.contractor_record_a.pk
        )

    def report(self, actor=None, start="2026-10-01", end="2026-10-31"):
        return own_individual_compensation_report_with_evidence(
            self.user_a if actor is None else actor,
            start,
            end,
        )

    def test_drafts_are_excluded(self):
        result = self.report()
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_approved_owned_compensation_has_evidence(self):
        self.approve_owned()
        result = self.report()
        self.assertEqual(len(result["employee_records"]), 1)
        self.assertEqual(len(result["contractor_records"]), 1)
        self.assertEqual(
            result["employee_records"][0]["payment_evidence"]["payment_evidence_status"],
            "Approved - Not Yet Issued",
        )

    def test_other_users_records_are_excluded(self):
        self.approve_owned()
        approve_employee_payroll_record(
            self.ceo, self.employee_record_b.pk
        )
        approve_contractor_payment_record(
            self.ceo, self.contractor_record_b.pk
        )

        result = self.report()

        self.assertEqual(
            {row["record_id"] for row in result["employee_records"]},
            {str(self.employee_record_a.pk)},
        )
        self.assertEqual(
            {row["record_id"] for row in result["contractor_records"]},
            {str(self.contractor_record_a.pk)},
        )

    def test_paid_records_include_verified_evidence(self):
        self.pay_owned()
        result = self.report()

        employee = result["employee_records"][0]["payment_evidence"]
        contractor = result["contractor_records"][0]["payment_evidence"]

        self.assertEqual(employee["payment_evidence_status"], "Paid")
        self.assertEqual(contractor["payment_evidence_status"], "Paid")
        self.assertTrue(contractor["settlement_independently_verified"])
        self.assertIsNotNone(contractor["settlement_date"])

    def test_amounts_and_periods_are_preserved(self):
        self.approve_owned()
        result = self.report()

        self.assertEqual(result["period_start"], "2026-10-01")
        self.assertEqual(result["period_end"], "2026-10-31")
        self.assertEqual(
            result["employee_records"][0]["net_amount"], "2000.00"
        )
        self.assertEqual(
            result["contractor_records"][0]["final_amount"], "500.00"
        )
        self.assertEqual(
            result["amount_basis"], "full_obligation_not_prorated"
        )

    def test_non_overlapping_period_excludes_records(self):
        self.approve_owned()
        result = self.report(
            start="2026-11-01", end="2026-11-30"
        )
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_unlinked_account_receives_no_compensation(self):
        self.approve_owned()
        result = self.report(actor=self.unlinked)
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_inactive_account_receives_no_compensation(self):
        self.approve_owned()
        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        result = self.report(actor=self.user_a)
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_sensitive_fields_remain_excluded(self):
        self.pay_owned()
        result = self.report()

        forbidden = {
            "transaction_reference",
            "supporting_evidence",
            "evidence_reference",
            "issued_by",
            "verified_by",
            "bank_account",
            "customer_email",
            "customer_phone",
        }

        for row in (
            result["employee_records"] + result["contractor_records"]
        ):
            self.assertFalse(forbidden.intersection(row))
            self.assertFalse(
                forbidden.intersection(row["payment_evidence"])
            )

    def test_report_is_read_only(self):
        self.approve_owned()

        self.employee_record_a.refresh_from_db()
        self.contractor_record_a.refresh_from_db()

        before_employee = self.employee_record_a.status
        before_contractor = self.contractor_record_a.status

        self.report()

        self.employee_record_a.refresh_from_db()
        self.contractor_record_a.refresh_from_db()

        self.assertEqual(self.employee_record_a.status, before_employee)
        self.assertEqual(self.contractor_record_a.status, before_contractor)