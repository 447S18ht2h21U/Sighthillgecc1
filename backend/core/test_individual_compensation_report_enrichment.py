"""Isolated ORM regression tests for compensation evidence enrichment."""

from django.test import TestCase
from django.utils import timezone

from .models import Role, User
from .access_compensation_scope import (
    own_contractor_payment_scope,
    own_employee_payroll_scope,
)
from .test_access_compensation_scope import (
    CompensationOwnershipScopeTests,
)
from .employee_payroll_services import (
    approve_employee_payroll_record,
    issue_employee_payroll_payment,
    mark_employee_payroll_paid,
)
from .contractor_payment_services import (
    approve_contractor_payment_record,
    mark_contractor_payment_paid,
)
from .contractor_payment_issuance_services import (
    issue_contractor_payment,
)
from .contractor_payment_settlement_services import (
    verify_contractor_payment_settlement,
)
from .individual_compensation_report_enrichment import (
    enrich_owned_contractor_payment_record,
    enrich_owned_employee_payroll_record,
)


class IndividualCompensationEnrichmentTests(TestCase):
    """Reuse fixture helpers without inheriting unrelated test methods."""

    make_employee = CompensationOwnershipScopeTests.make_employee
    make_contractor = CompensationOwnershipScopeTests.make_contractor
    make_employee_record = CompensationOwnershipScopeTests.make_employee_record
    make_contractor_record = CompensationOwnershipScopeTests.make_contractor_record

    def setUp(self):
        CompensationOwnershipScopeTests.setUp(self)
        self.ceo = User.objects.create_user(
            username="enrichment_test_ceo",
            role=Role.CEO,
            initials="ET",
        )

    def employee(self):
        return own_employee_payroll_scope(self.user_a).get(
            pk=self.employee_record_a.pk
        )

    def contractor(self):
        return own_contractor_payment_scope(self.user_a).get(
            pk=self.contractor_record_a.pk
        )

    def approve_employee(self):
        approve_employee_payroll_record(
            self.ceo, self.employee_record_a.pk
        )

    def approve_contractor(self):
        approve_contractor_payment_record(
            self.ceo, self.contractor_record_a.pk
        )

    def issue_employee(self):
        self.approve_employee()
        issue_employee_payroll_payment(
            self.ceo,
            self.employee_record_a.pk,
            self.employee_record_a.net_amount,
            "ACH",
            f"ENRICH-EMP-{self.employee_record_a.pk}",
        )

    def issue_contractor(self):
        self.approve_contractor()
        issue_contractor_payment(
            self.ceo,
            self.contractor_record_a.pk,
            self.contractor_record_a.final_amount,
            "ACH",
            f"ENRICH-CTR-{self.contractor_record_a.pk}",
            "Isolated enrichment test issuance evidence",
        )

    def verify_contractor(self):
        self.issue_contractor()
        verify_contractor_payment_settlement(
            self.admin,
            self.contractor_record_a.pk,
            timezone.localdate(),
            self.contractor_record_a.final_amount,
            f"ENRICH-BANK-{self.contractor_record_a.pk}",
        )

    def test_employee_approved_without_issuance(self):
        self.approve_employee()
        result = enrich_owned_employee_payroll_record(self.employee())
        self.assertEqual(
            result["payment_evidence_status"],
            "Approved - Not Yet Issued",
        )
        self.assertIsNone(result["payment_issued_at"])

    def test_employee_issued_not_marked_paid(self):
        self.issue_employee()
        result = enrich_owned_employee_payroll_record(self.employee())
        self.assertEqual(
            result["payment_evidence_status"],
            "Payment Issued - Not Yet Marked Paid",
        )
        self.assertIsNotNone(result["payment_issued_at"])

    def test_employee_paid_uses_authorized_workflow(self):
        self.issue_employee()
        mark_employee_payroll_paid(
            self.admin, self.employee_record_a.pk
        )
        result = enrich_owned_employee_payroll_record(self.employee())
        self.assertEqual(result["payment_evidence_status"], "Paid")
        self.assertFalse(result["settlement_independently_verified"])

    def test_employee_has_no_inferred_project(self):
        self.approve_employee()
        result = enrich_owned_employee_payroll_record(self.employee())
        self.assertEqual(
            result["project_association"],
            "Not applicable to employee payroll",
        )

    def test_contractor_without_project(self):
        self.approve_contractor()
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        self.assertEqual(
            result["project_association"],
            "Not assigned to a project",
        )
        self.assertIsNone(result["project_code"])

    def test_contractor_approved_without_issuance(self):
        self.approve_contractor()
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        self.assertEqual(
            result["payment_evidence_status"],
            "Approved - Not Yet Issued",
        )

    def test_contractor_issued_not_settled(self):
        self.issue_contractor()
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        self.assertEqual(
            result["payment_evidence_status"],
            "Payment Issued - Not Yet Marked Paid",
        )
        self.assertFalse(result["settlement_independently_verified"])

    def test_contractor_verified_not_marked_paid(self):
        self.verify_contractor()
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        self.assertEqual(
            result["payment_evidence_status"],
            "Settlement Verified - Not Yet Marked Paid",
        )
        self.assertTrue(result["settlement_independently_verified"])
        self.assertIsNotNone(result["settlement_date"])

    def test_contractor_paid_with_settlement(self):
        self.verify_contractor()
        mark_contractor_payment_paid(
            self.admin, self.contractor_record_a.pk
        )
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        self.assertEqual(result["payment_evidence_status"], "Paid")
        self.assertTrue(result["settlement_independently_verified"])

    def test_historical_msr_not_inferred(self):
        self.approve_contractor()
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        self.assertEqual(
            result["historical_msr_attribution"],
            "Historical MSR version not established",
        )

    def test_sensitive_evidence_not_exposed(self):
        self.verify_contractor()
        result = enrich_owned_contractor_payment_record(
            self.contractor()
        )
        forbidden = {
            "transaction_reference",
            "evidence_reference",
            "supporting_evidence",
            "issued_by",
            "verified_by",
            "customer_email",
            "customer_phone",
            "bank_account",
        }
        self.assertFalse(forbidden.intersection(result.keys()))

    def test_enrichment_does_not_modify_payment_status(self):
        self.approve_employee()
        self.approve_contractor()

        enrich_owned_employee_payroll_record(self.employee())
        enrich_owned_contractor_payment_record(self.contractor())

        self.employee_record_a.refresh_from_db()
        self.contractor_record_a.refresh_from_db()

        self.assertEqual(self.employee_record_a.status, "APPROVED")
        self.assertEqual(self.contractor_record_a.status, "APPROVED")