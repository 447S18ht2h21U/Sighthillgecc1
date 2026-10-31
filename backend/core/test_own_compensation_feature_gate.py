"""The contractor role gate must not enable broader reports."""

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .access_compensation_report_permissions import (
    require_own_compensation_permission,
)
from .access_own_contractor_payment_permissions import (
    require_own_contractor_payment_permission,
)
from .access_permission_catalog import has_permission
from .models import Role, User


class OwnCompensationFeatureGateTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="contractor_gate_3724",
            role=Role.TECHNICIAN,
            initials="CG",
        )

    def test_disabled_gate_denies_contractor_and_shared(self):
        with self.assertRaises(PermissionDenied):
            require_own_contractor_payment_permission(self.actor)
        with self.assertRaises(PermissionDenied):
            require_own_compensation_permission(self.actor)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_enabled_gate_allows_only_contractor_boundary(self):
        require_own_contractor_payment_permission(self.actor)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_shared_report_remains_denied_even_with_gate_enabled(self):
        with self.assertRaises(PermissionDenied):
            require_own_compensation_permission(self.actor)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_inactive_and_unknown_roles_are_denied(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            require_own_contractor_payment_permission(self.actor)

        self.actor.is_active = True
        self.actor.role = "INVALID_ROLE"
        self.actor.save(update_fields=["is_active", "role"])
        with self.assertRaises(PermissionDenied):
            require_own_contractor_payment_permission(self.actor)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_unrelated_permissions_remain_default_deny(self):
        for code in (
            "compensation.all.view",
            "payroll_payments.approve",
            "financials.operations.view",
            "users.manage",
            "technician_assignments.create",
        ):
            with self.subTest(code=code):
                self.assertFalse(has_permission(self.actor, code))
