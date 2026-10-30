"""Ownership enforcement tests for compensation evidence retrieval."""

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.exceptions import NotFound

from .models import Role, User
from .test_access_compensation_scope import CompensationOwnershipScopeTests
from .employee_payroll_services import approve_employee_payroll_record
from .contractor_payment_services import approve_contractor_payment_record
from .individual_compensation_report_authorized_enrichment import (
    authorized_employee_payroll_enrichment,
    authorized_contractor_payment_enrichment,
)


class AuthorizedCompensationEnrichmentTests(TestCase):
    """Reuse fixture helpers without inheriting unrelated tests."""

    make_employee = CompensationOwnershipScopeTests.make_employee
    make_contractor = CompensationOwnershipScopeTests.make_contractor
    make_employee_record = CompensationOwnershipScopeTests.make_employee_record
    make_contractor_record = CompensationOwnershipScopeTests.make_contractor_record

    def setUp(self):
        CompensationOwnershipScopeTests.setUp(self)
        self.ceo = User.objects.create_user(
            username="authorized_enrichment_test_ceo",
            role=Role.CEO,
            initials="AE",
        )
        for record in (
            self.employee_record_a,
            self.employee_record_b,
        ):
            approve_employee_payroll_record(self.ceo, record.pk)
        for record in (
            self.contractor_record_a,
            self.contractor_record_b,
        ):
            approve_contractor_payment_record(self.ceo, record.pk)

    def test_employee_can_retrieve_own_record(self):
        result = authorized_employee_payroll_enrichment(
            self.user_a, self.employee_record_a.pk
        )
        self.assertEqual(
            result["payment_evidence_status"],
            "Approved - Not Yet Issued",
        )

    def test_contractor_can_retrieve_own_record(self):
        result = authorized_contractor_payment_enrichment(
            self.user_a, self.contractor_record_a.pk
        )
        self.assertEqual(
            result["payment_evidence_status"],
            "Approved - Not Yet Issued",
        )

    def test_other_employee_record_is_not_found(self):
        with self.assertRaises(NotFound):
            authorized_employee_payroll_enrichment(
                self.user_a, self.employee_record_b.pk
            )

    def test_other_contractor_record_is_not_found(self):
        with self.assertRaises(NotFound):
            authorized_contractor_payment_enrichment(
                self.user_a, self.contractor_record_b.pk
            )

    def test_unknown_record_is_not_found(self):
        with self.assertRaises(NotFound):
            authorized_employee_payroll_enrichment(
                self.user_a, 999999999
            )

    def test_unlinked_account_is_denied(self):
        for function, record in (
            (authorized_employee_payroll_enrichment, self.employee_record_a),
            (authorized_contractor_payment_enrichment, self.contractor_record_a),
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(NotFound):
                    function(self.unlinked, record.pk)

    def test_inactive_account_is_denied(self):
        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])
        for function, record in (
            (authorized_employee_payroll_enrichment, self.employee_record_a),
            (authorized_contractor_payment_enrichment, self.contractor_record_a),
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(NotFound):
                    function(self.user_a, record.pk)

    def test_anonymous_and_missing_users_denied(self):
        for actor in (None, AnonymousUser()):
            for function, record in (
                (authorized_employee_payroll_enrichment, self.employee_record_a),
                (authorized_contractor_payment_enrichment, self.contractor_record_a),
            ):
                with self.subTest(actor=type(actor).__name__, function=function.__name__):
                    with self.assertRaises(NotFound):
                        function(actor, record.pk)

    def test_invalid_record_identifiers_denied(self):
        for record_id in (None, True, False, [], {}, "", " ", "abc", -1):
            with self.subTest(record_id=str(record_id)):
                with self.assertRaises(NotFound):
                    authorized_employee_payroll_enrichment(
                        self.user_a, record_id
                    )

    def test_role_does_not_override_ownership(self):
        self.user_a.role = Role.CEO
        self.user_a.save(update_fields=["role"])
        with self.assertRaises(NotFound):
            authorized_employee_payroll_enrichment(
                self.user_a, self.employee_record_b.pk
            )
        with self.assertRaises(NotFound):
            authorized_contractor_payment_enrichment(
                self.user_a, self.contractor_record_b.pk
            )

    def test_sensitive_fields_not_disclosed(self):
        result = authorized_contractor_payment_enrichment(
            self.user_a, self.contractor_record_a.pk
        )
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
        self.assertFalse(forbidden.intersection(result))

    def test_authorized_read_does_not_modify_payment_status(self):
        authorized_employee_payroll_enrichment(
            self.user_a, self.employee_record_a.pk
        )
        authorized_contractor_payment_enrichment(
            self.user_a, self.contractor_record_a.pk
        )
        self.employee_record_a.refresh_from_db()
        self.contractor_record_a.refresh_from_db()
        self.assertEqual(self.employee_record_a.status, "APPROVED")
        self.assertEqual(self.contractor_record_a.status, "APPROVED")