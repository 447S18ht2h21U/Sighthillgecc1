"""Database-backed presentation checks; no operational API registration."""
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import AuditHead, AuditEvent, Outbox, Role, User
from .test_access_compensation_scope import CompensationOwnershipScopeTests
from .employee_payroll_services import approve_employee_payroll_record
from .contractor_payment_services import approve_contractor_payment_record
from .individual_compensation_report_with_evidence import (
    own_individual_compensation_report_with_evidence,
)
from .payroll_personal_presentation_4286 import (
    permitted_personal_payroll_presentation,
    present_authorized_personal_report,
)


class PayrollPersonalPresentation4286Tests(TestCase):
    make_employee = CompensationOwnershipScopeTests.make_employee
    make_contractor = CompensationOwnershipScopeTests.make_contractor
    make_employee_record = CompensationOwnershipScopeTests.make_employee_record
    make_contractor_record = CompensationOwnershipScopeTests.make_contractor_record

    def setUp(self):
        CompensationOwnershipScopeTests.setUp(self)
        self.ceo = User.objects.create_user(
            username="payroll_adapter_4286_ceo",
            role=Role.CEO,
            initials="PA",
        )

    def approve_both(self, suffix="a"):
        approve_employee_payroll_record(
            self.ceo, getattr(self, "employee_record_" + suffix).pk
        )
        approve_contractor_payment_record(
            self.ceo, getattr(self, "contractor_record_" + suffix).pk
        )

    def owned_report(self, actor=None):
        return own_individual_compensation_report_with_evidence(
            self.user_a if actor is None else actor,
            "2026-10-01",
            "2026-10-31",
        )

    def test_drafts_are_not_presented(self):
        result = present_authorized_personal_report(self.owned_report())
        self.assertEqual(result["employee_records"], [])
        self.assertEqual(result["contractor_records"], [])

    def test_approved_pay_is_formatted_but_not_claimed_paid(self):
        self.approve_both()
        result = present_authorized_personal_report(self.owned_report())

        self.assertEqual(result["view"], "my_compensation")
        self.assertEqual(len(result["employee_records"]), 1)
        self.assertEqual(len(result["contractor_records"]), 1)

        for key in ("employee_records", "contractor_records"):
            row = result[key][0]
            self.assertEqual(row["status"], "APPROVED")
            self.assertEqual(
                row["status_label"], "Approved - Not Yet Paid"
            )
            self.assertEqual(
                row["payment_evidence_status"],
                "Approved - Not Yet Issued"
            )
            self.assertIsNone(row["scheduled_payment_date"])
            self.assertIsNone(row["actual_paid_date"])

    def test_personal_report_excludes_other_users_and_private_fields(self):
        self.approve_both("a")
        self.approve_both("b")

        result = present_authorized_personal_report(self.owned_report())

        self.assertEqual(len(result["employee_records"]), 1)
        self.assertEqual(len(result["contractor_records"]), 1)

        serialized = str(result).lower()
        for forbidden in (
            "scope employee b",
            "scope-emp-b",
            "scope contractor b",
            "scope-ctr-b",
            "bank_account",
            "taxpayer_id",
            "transaction_reference",
            "supporting_evidence",
            "record_id",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_inactive_and_unlinked_accounts_receive_empty_reports(self):
        self.approve_both()

        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        for actor in (self.user_a, self.unlinked):
            with self.subTest(actor=actor.username):
                result = present_authorized_personal_report(
                    self.owned_report(actor)
                )
                self.assertEqual(result["employee_records"], [])
                self.assertEqual(result["contractor_records"], [])

    def test_public_entry_stays_default_deny_even_for_executives(self):
        self.approve_both()

        for actor in (self.user_a, self.ceo, self.admin):
            with self.subTest(actor=actor.username):
                with self.assertRaises(PermissionDenied):
                    permitted_personal_payroll_presentation(
                        actor, "2026-10-01", "2026-10-31"
                    )

    def test_presentation_does_not_change_payment_or_audit_records(self):
        self.approve_both()

        before_head = AuditHead.objects.values_list(
            "sequence", "digest"
        ).get(pk=1)
        before_events = AuditEvent.objects.count()
        before_outbox = Outbox.objects.count()

        result = present_authorized_personal_report(self.owned_report())
        self.assertEqual(len(result["employee_records"]), 1)

        self.assertEqual(
            AuditHead.objects.values_list(
                "sequence", "digest"
            ).get(pk=1),
            before_head,
        )
        self.assertEqual(AuditEvent.objects.count(), before_events)
        self.assertEqual(Outbox.objects.count(), before_outbox)

    def test_rejects_malformed_or_unapproved_report_payloads(self):
        with self.assertRaises(ValueError):
            present_authorized_personal_report({})

        base = self.owned_report()

        with self.assertRaises(ValueError):
            present_authorized_personal_report({
                **base, "evidence_basis": "not_verified"
            })

        with self.assertRaises(ValueError):
            present_authorized_personal_report({
                **base, "employee_records": [{
                    "record_type": "employee_payroll",
                    "status": "DRAFT",
                }],
            })