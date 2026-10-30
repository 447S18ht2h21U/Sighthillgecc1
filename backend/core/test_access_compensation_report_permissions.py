"""Default-deny tests for personal compensation report permissions."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied

from .access_permission_catalog import (
    PERMISSION_BY_CODE,
    has_permission,
)
from .access_position_proposals import (
    proposed_permissions,
    proposed_access_granted,
)
from .access_position_templates import position_grants_permission
from .access_compensation_report_permissions import (
    OWN_COMPENSATION_PERMISSION,
    permitted_own_compensation_report,
    require_own_compensation_permission,
)


class CompensationReportPermissionGateTests(SimpleTestCase):

    def test_missing_and_anonymous_users_denied(self):
        for actor in (
            None,
            SimpleNamespace(is_authenticated=False, is_active=True),
        ):
            with self.subTest(actor=repr(actor)):
                with self.assertRaises(PermissionDenied):
                    require_own_compensation_permission(actor)

    def test_executive_roles_do_not_bypass_gate(self):
        for role in ("CEO", "COMPTROLLER"):
            actor = SimpleNamespace(
                role=role,
                is_authenticated=True,
                is_active=True,
            )
            with self.subTest(role=role):
                with self.assertRaises(PermissionDenied):
                    require_own_compensation_permission(actor)

    def test_position_proposals_never_grant_access(self):
        for role in (
            "CEO",
            "SALES_ASSOCIATE",
            "SALES_MANAGER",
            "COMPTROLLER",
            "INSTALLATION_MANAGER",
            "TECHNICIAN",
            "ACCOUNTS_PAYABLE_ASSOCIATE",
            "DATABASE_ADMINISTRATOR",
        ):
            with self.subTest(role=role):
                self.assertIn(
                    OWN_COMPENSATION_PERMISSION,
                    proposed_permissions(role),
                )
                self.assertFalse(
                    position_grants_permission(
                        role, OWN_COMPENSATION_PERMISSION
                    )
                )
                self.assertFalse(
                    proposed_access_granted(
                        SimpleNamespace(role=role),
                        OWN_COMPENSATION_PERMISSION,
                    )
                )

    def test_unknown_permissions_do_not_authorize(self):
        self.assertIn(
            OWN_COMPENSATION_PERMISSION,
            PERMISSION_BY_CODE,
        )
        self.assertNotIn(
            "compensation.unknown.view",
            PERMISSION_BY_CODE,
        )
        self.assertFalse(
            has_permission(None, "compensation.unknown.view")
        )

    def test_denied_request_never_invokes_report(self):
        actor = SimpleNamespace(
            role="CEO",
            is_authenticated=True,
            is_active=True,
        )

        with patch(
            "core.access_compensation_report_permissions."
            "own_individual_compensation_report_with_evidence"
        ) as report:
            with self.assertRaises(PermissionDenied):
                permitted_own_compensation_report(
                    actor,
                    "2026-10-01",
                    "2026-10-31",
                )

            report.assert_not_called()

    def test_catalog_remains_default_deny(self):
        codes_before = tuple(PERMISSION_BY_CODE)

        for code in codes_before:
            with self.subTest(code=code):
                self.assertFalse(
                    has_permission(
                        SimpleNamespace(
                            is_authenticated=True,
                            is_active=True,
                            role="CEO",
                        ),
                        code,
                    )
                )

        self.assertEqual(
            tuple(PERMISSION_BY_CODE),
            codes_before,
        )