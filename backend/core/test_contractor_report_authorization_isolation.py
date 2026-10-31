"""Cross-report isolation for contractor-only compensation access."""

from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .access_compensation_report_permissions import (
    permitted_own_compensation_report,
    require_own_compensation_permission,
)
from .access_own_contractor_payment_permissions import (
    require_own_contractor_payment_permission,
)
from .access_permission_catalog import has_permission
from .models import Role, User


class ContractorReportAuthorizationIsolationTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="cross_report_isolation_3726",
            role=Role.TECHNICIAN,
            initials="CR",
        )

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_contractor_gate_does_not_grant_shared_report(self):
        require_own_contractor_payment_permission(self.actor)

        with self.assertRaises(PermissionDenied):
            require_own_compensation_permission(self.actor)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_shared_report_cannot_retrieve_financial_evidence(self):
        with patch(
            "core.access_compensation_report_permissions."
            "own_individual_compensation_report_with_evidence"
        ) as report:
            with self.assertRaises(PermissionDenied):
                permitted_own_compensation_report(
                    self.actor, "2026-10-01", "2026-10-31"
                )
            report.assert_not_called()

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_financial_and_approval_permissions_stay_denied(self):
        require_own_contractor_payment_permission(self.actor)

        for code in (
            "compensation.all.view",
            "financials.operations.view",
            "payroll_payments.approve",
            "users.manage",
            "technician_assignments.create",
        ):
            with self.subTest(code=code):
                self.assertFalse(has_permission(self.actor, code))

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=False)
    def test_disabled_contractor_gate_denies_both_reports(self):
        with self.assertRaises(PermissionDenied):
            require_own_contractor_payment_permission(self.actor)

        with self.assertRaises(PermissionDenied):
            require_own_compensation_permission(self.actor)