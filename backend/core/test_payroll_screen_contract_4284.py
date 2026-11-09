"""Test-only payroll screen contract verification; no live API or role grants.

Uses existing database-backed ownership fixtures and existing business
services, with the independently verified disposable SQLite audit runner.
"""
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import AuditHead, AuditEvent, Outbox, Role, User
from .test_access_compensation_scope import CompensationOwnershipScopeTests
from .employee_payroll_services import approve_employee_payroll_record
from .contractor_payment_services import approve_contractor_payment_record
from .individual_compensation_report_with_evidence import (
    own_individual_compensation_report_with_evidence,
)
from .access_compensation_report_permissions import (
    permitted_own_compensation_report,
)


class PayrollScreenContract4284Tests(TestCase):
    make_employee = CompensationOwnershipScopeTests.make_employee
    make_contractor = CompensationOwnershipScopeTests.make_contractor
    make_employee_record = CompensationOwnershipScopeTests.make_employee_record
    make_contractor_record = CompensationOwnershipScopeTests.make_contractor_record

    def setUp(self):
        CompensationOwnershipScopeTests.setUp(self)
        self.ceo = User.objects.create_user(
            username="payroll_screen_4284_ceo",
            role=Role.CEO,
            initials="PS",
        )

    def approve(self, identity="a"):
        employee = getattr(self, "employee_record_" + identity)
        contractor = getattr(self, "contractor_record_" + identity)
        approve_employee_payroll_record(self.ceo, employee.pk)
        approve_contractor_payment_record(self.ceo, contractor.pk)

    def report(self, actor=None):
        return own_individual_compensation_report_with_evidence(
            self.user_a if actor is None else actor,
            "2026-10-01",
            "2026-10-31",
        )

    def test_draft_employee_and_contractor_pay_never_appear(self):
        result = self.report()
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_approved_self_pay_has_distinct_types_and_status(self):
        self.approve()
        result = self.report()
        self.assertEqual(len(result["employee_records"]), 1)
        self.assertEqual(len(result["contractor_records"]), 1)

        employee = result["employee_records"][0]
        contractor = result["contractor_records"][0]

        self.assertEqual(employee["record_type"], "employee_payroll")
        self.assertEqual(contractor["record_type"], "contractor_payment")
        self.assertEqual(employee["status"], "APPROVED")
        self.assertEqual(contractor["status"], "APPROVED")
        self.assertEqual(
            employee["status_label"], "Approved - Not Yet Paid"
        )
        self.assertEqual(
            contractor["status_label"], "Approved - Not Yet Paid"
        )

    def test_each_user_receives_only_own_record_identifiers(self):
        self.approve("a")
        self.approve("b")

        for actor, expected_employee, expected_contractor in (
            (self.user_a, self.employee_record_a, self.contractor_record_a),
            (self.user_b, self.employee_record_b, self.contractor_record_b),
        ):
            with self.subTest(actor=actor.username):
                result = self.report(actor)
                self.assertEqual(
                    [row["record_id"] for row in result["employee_records"]],
                    [str(expected_employee.pk)],
                )
                self.assertEqual(
                    [row["record_id"] for row in result["contractor_records"]],
                    [str(expected_contractor.pk)],
                )

    def test_approved_records_show_evidence_without_claiming_payment(self):
        self.approve()
        result = self.report()

        self.assertEqual(
            result["evidence_basis"],
            "ownership_verified_per_record",
        )
        for key in ("employee_records", "contractor_records"):
            row = result[key][0]
            self.assertEqual(
                row["payment_evidence"]["payment_evidence_status"],
                "Approved - Not Yet Issued",
            )
            self.assertNotEqual(row["status"], "PAID")

    def test_broad_compensation_permission_stays_default_deny(self):
        self.approve()

        for actor in (self.user_a, self.ceo, self.admin):
            with self.subTest(actor=actor.username):
                with self.assertRaises(PermissionDenied):
                    permitted_own_compensation_report(
                        actor, "2026-10-01", "2026-10-31"
                    )

    def test_inactive_or_unlinked_accounts_receive_no_records(self):
        self.approve()
        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        self.assertEqual(self.report(self.user_a)["employee_records"], [])
        self.assertEqual(self.report(self.user_a)["contractor_records"], [])

        result = self.report(self.unlinked)
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_read_only_reporting_preserves_audit_and_payment_state(self):
        self.approve()

        head_before = tuple(
            AuditHead.objects.values_list("sequence", "digest").get(pk=1)
        )
        events_before = AuditEvent.objects.count()
        outbox_before = Outbox.objects.count()
        employee_before = (
            self.employee_record_a.__class__.objects.get(
                pk=self.employee_record_a.pk
            ).status
        )
        contractor_before = (
            self.contractor_record_a.__class__.objects.get(
                pk=self.contractor_record_a.pk
            ).status
        )

        report = self.report()
        self.assertEqual(len(report["employee_records"]), 1)
        self.assertEqual(len(report["contractor_records"]), 1)

        self.assertEqual(
            tuple(AuditHead.objects.values_list(
                "sequence", "digest"
            ).get(pk=1)),
            head_before,
        )
        self.assertEqual(AuditEvent.objects.count(), events_before)
        self.assertEqual(Outbox.objects.count(), outbox_before)
        self.assertEqual(
            self.employee_record_a.__class__.objects.get(
                pk=self.employee_record_a.pk
            ).status,
            employee_before,
        )
        self.assertEqual(
            self.contractor_record_a.__class__.objects.get(
                pk=self.contractor_record_a.pk
            ).status,
            contractor_before,
        )