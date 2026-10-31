"""Isolated tests for non-operational own-compensation role eligibility."""

from django.test import SimpleTestCase

from .access_own_compensation_role_policy import (
    ELIGIBLE_ROLES,
    own_compensation_role_eligible,
    own_compensation_policy_grants_live_access,
)
from .access_permission_catalog import has_permission
from .models import Role


class OwnCompensationRolePolicyTests(SimpleTestCase):
    def eligible(self, role, **changes):
        fields = {
            "role": role,
            "permission_code": "compensation.own.view",
            "authenticated": True,
            "active": True,
        }
        fields.update(changes)
        return own_compensation_role_eligible(**fields)

    def test_exact_nine_model_roles(self):
        self.assertEqual(
            ELIGIBLE_ROLES,
            frozenset(value for value, label in Role.choices),
        )
        self.assertEqual(len(ELIGIBLE_ROLES), 9)

    def test_all_known_roles_eligible_for_own_compensation_only(self):
        for role in ELIGIBLE_ROLES:
            with self.subTest(role=role):
                self.assertTrue(self.eligible(role))

    def test_unknown_role_denied(self):
        for role in (None, "", "SUPERUSER", "UNKNOWN", "ceo"):
            with self.subTest(role=role):
                self.assertFalse(self.eligible(role))

    def test_inactive_and_unauthenticated_denied(self):
        for changes in (
            {"active": False},
            {"active": None},
            {"authenticated": False},
            {"authenticated": None},
            {"active": 1},
            {"authenticated": 1},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.eligible(Role.TECHNICIAN, **changes))

    def test_other_permissions_never_eligible(self):
        for code in (
            "compensation.all.view",
            "payroll_payments.approve",
            "financials.operations.view",
            "users.manage",
            "technician_assignments.create",
            None,
        ):
            with self.subTest(code=code):
                self.assertFalse(
                    self.eligible(Role.CEO, permission_code=code)
                )

    def test_eligibility_never_grants_live_access(self):
        for role in ELIGIBLE_ROLES:
            with self.subTest(role=role):
                self.assertFalse(
                    own_compensation_policy_grants_live_access(role=role)
                )

    def test_central_evaluator_remains_default_deny(self):
        self.assertFalse(
            has_permission(None, "compensation.own.view")
        )
        self.assertFalse(
            has_permission(None, "compensation.all.view")
        )