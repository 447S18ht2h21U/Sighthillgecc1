"""Regression tests for financial report service authorization."""

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import Role, User


class FinancialReportingAuthorizationTests(TestCase):
    def setUp(self):
        self.sales_manager = User.objects.create_user(
            username="report_auth_sales_manager",
            password="test-password",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.comptroller = User.objects.create_user(
            username="report_auth_comptroller",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.sales_associate = User.objects.create_user(
            username="report_auth_sales_associate",
            password="test-password",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.ceo = User.objects.create_user(
            username="report_auth_ceo",
            password="test-password",
            role=Role.CEO,
            initials="CE",
        )

    def require_role(self, actor, required_role):
        from .financial_reporting_authorization import (
            require_financial_reporting_role,
        )
        return require_financial_reporting_role(
            actor,
            required_role,
        )

    def test_active_sales_manager_can_use_commission_reporting(self):
        current = self.require_role(
            self.sales_manager,
            Role.SALES_MANAGER,
        )
        self.assertEqual(current.pk, self.sales_manager.pk)

    def test_active_comptroller_can_use_payroll_reporting(self):
        current = self.require_role(
            self.comptroller,
            Role.COMPTROLLER,
        )
        self.assertEqual(current.pk, self.comptroller.pk)

    def test_sales_associate_cannot_use_commission_reporting(self):
        with self.assertRaises(PermissionDenied):
            self.require_role(
                self.sales_associate,
                Role.SALES_MANAGER,
            )

    def test_ceo_cannot_use_comptroller_reporting(self):
        with self.assertRaises(PermissionDenied):
            self.require_role(
                self.ceo,
                Role.COMPTROLLER,
            )

    def test_inactive_sales_manager_is_rejected(self):
        self.sales_manager.is_active = False
        self.sales_manager.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.require_role(
                self.sales_manager,
                Role.SALES_MANAGER,
            )

    def test_inactive_comptroller_is_rejected(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.require_role(
                self.comptroller,
                Role.COMPTROLLER,
            )

    def test_stale_role_object_does_not_grant_authority(self):
        User.objects.filter(pk=self.sales_manager.pk).update(
            role=Role.SALES_ASSOCIATE,
        )

        with self.assertRaises(PermissionDenied):
            self.require_role(
                self.sales_manager,
                Role.SALES_MANAGER,
            )

    def test_missing_actor_is_rejected(self):
        with self.assertRaises(PermissionDenied):
            self.require_role(None, Role.COMPTROLLER)

    def test_unsaved_actor_is_rejected(self):
        actor = User(
            username="unsaved_reporting_actor",
            role=Role.COMPTROLLER,
        )

        with self.assertRaises(PermissionDenied):
            self.require_role(actor, Role.COMPTROLLER)