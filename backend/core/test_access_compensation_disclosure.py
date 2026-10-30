"""Regression tests for safe individual compensation disclosure."""

from django.contrib.auth.models import AnonymousUser

from .access_compensation_disclosure import (
    own_contractor_payment_disclosure,
    own_employee_payroll_disclosure,
)
from .models import ContractorPaymentRecord, EmployeePayrollRecord
from . import test_access_compensation_scope as ownership_fixtures
from .models import Role, User
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



class CompensationDisclosureTests(ownership_fixtures.CompensationOwnershipScopeTests):
    """Reuse isolated employee and contractor financial test fixtures.

    Inherited ownership tests also run here; disclosure-specific tests
    validate status filtering and limited public response fields.
    """

    def setUp(self):
        super().setUp()
        self.ceo = User.objects.create_user(
            username="disclosure_test_ceo",
            role=Role.CEO,
            initials="DC",
        )

    def _approve_employee(self, record):
        approve_employee_payroll_record(self.ceo, record.pk)

    def _approve_contractor(self, record):
        approve_contractor_payment_record(self.ceo, record.pk)

    def _pay_employee(self, record):
        self._approve_employee(record)
        issue_employee_payroll_payment(
            self.ceo,
            record.pk,
            record.net_amount,
            "ACH",
            f"DISCLOSURE-TEST-{record.pk}",
        )
        mark_employee_payroll_paid(self.admin, record.pk)

    def _pay_contractor(self, record):
        from django.utils import timezone

        self._approve_contractor(record)

        issue_contractor_payment(
            self.ceo,
            record.pk,
            record.final_amount,
            "ACH",
            f"DISCLOSURE-CONTRACTOR-{record.pk}",
            "Contractor payment disclosure test evidence",
        )

        verify_contractor_payment_settlement(
            self.admin,
            record.pk,
            timezone.localdate(),
            record.final_amount,
            f"DISCLOSURE-BANK-{record.pk}",
        )

        mark_contractor_payment_paid(self.admin, record.pk)

    def test_draft_compensation_is_not_disclosed(self):
        self.assertEqual(own_employee_payroll_disclosure(self.user_a), [])
        self.assertEqual(own_contractor_payment_disclosure(self.user_a), [])

    def test_approved_compensation_is_not_labeled_paid(self):
        self._approve_employee(self.employee_record_a)

        self._approve_contractor(self.contractor_record_a)

        employee = own_employee_payroll_disclosure(self.user_a)
        contractor = own_contractor_payment_disclosure(self.user_a)

        self.assertEqual(len(employee), 1)
        self.assertEqual(len(contractor), 1)
        self.assertEqual(employee[0]["status"], "APPROVED")
        self.assertEqual(contractor[0]["status"], "APPROVED")
        self.assertEqual(
            employee[0]["status_label"], "Approved - Not Yet Paid"
        )
        self.assertEqual(
            contractor[0]["status_label"], "Approved - Not Yet Paid"
        )

    def test_paid_compensation_is_correctly_labeled(self):
        self._pay_employee(self.employee_record_a)

        self._pay_contractor(self.contractor_record_a)

        employee = own_employee_payroll_disclosure(self.user_a)
        contractor = own_contractor_payment_disclosure(self.user_a)

        self.assertEqual(employee[0]["status_label"], "Paid")
        self.assertEqual(contractor[0]["status_label"], "Paid")

    def test_other_peoples_records_are_never_disclosed(self):
        for record in (self.employee_record_a, self.employee_record_b):
            self._approve_employee(record)
        for record in (self.contractor_record_a, self.contractor_record_b):
            self._approve_contractor(record)

        employee = own_employee_payroll_disclosure(self.user_a)
        contractor = own_contractor_payment_disclosure(self.user_a)

        self.assertEqual(
            {item["record_id"] for item in employee},
            {str(self.employee_record_a.pk)},
        )
        self.assertEqual(
            {item["record_id"] for item in contractor},
            {str(self.contractor_record_a.pk)},
        )

    def test_sensitive_internal_fields_are_excluded(self):
        self._approve_employee(self.employee_record_a)

        self._approve_contractor(self.contractor_record_a)

        forbidden = {
            "calculation_snapshot",
            "compensation_terms",
            "approved_by",
            "approved_at",
            "created_by",
            "issued_by",
            "transaction_reference",
            "supporting_evidence",
            "employee_id",
            "contractor_id",
            "user_id",
        }

        for result in (
            own_employee_payroll_disclosure(self.user_a),
            own_contractor_payment_disclosure(self.user_a),
        ):
            self.assertEqual(len(result), 1)
            self.assertFalse(forbidden.intersection(result[0]))

    def test_inactive_unlinked_and_anonymous_accounts_receive_nothing(self):
        for record in (self.employee_record_a, self.employee_record_b):
            self._approve_employee(record)
        for record in (self.contractor_record_a, self.contractor_record_b):
            self._approve_contractor(record)

        for actor in (None, AnonymousUser(), self.unlinked):
            self.assertEqual(own_employee_payroll_disclosure(actor), [])
            self.assertEqual(own_contractor_payment_disclosure(actor), [])

        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        self.assertEqual(own_employee_payroll_disclosure(self.user_a), [])
        self.assertEqual(own_contractor_payment_disclosure(self.user_a), [])

    def test_disclosed_amounts_are_formatted_and_distinct(self):
        self._approve_employee(self.employee_record_a)

        self._approve_contractor(self.contractor_record_a)

        employee = own_employee_payroll_disclosure(self.user_a)[0]
        contractor = own_contractor_payment_disclosure(self.user_a)[0]

        self.assertEqual(employee["gross_amount"], "2500.00")
        self.assertEqual(employee["deduction_amount"], "500.00")
        self.assertEqual(employee["net_amount"], "2000.00")

        self.assertEqual(contractor["basis_amount"], "500.00")
        self.assertEqual(contractor["deduction_amount"], "0.00")
        self.assertEqual(contractor["final_amount"], "500.00")

        self.assertEqual(employee["record_type"], "employee_payroll")
        self.assertEqual(contractor["record_type"], "contractor_payment")
