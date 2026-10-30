"""Service-boundary security tests for payroll summaries."""

from datetime import date

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import PayrollSummary, Role, User
from .payroll_summary_services import (
    approve_payroll_summary,
    create_payroll_summary,
)


class PayrollSummaryServiceSecurityTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="payroll_security_comptroller",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="payroll_security_ceo",
            password="test-password",
            role=Role.CEO,
            initials="CE",
        )
        self.sales_manager = User.objects.create_user(
            username="payroll_security_manager",
            password="test-password",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.start = date(2026, 10, 1)
        self.end = date(2026, 10, 15)

    def draft(self):
        return create_payroll_summary(
            self.comptroller,
            self.start,
            self.end,
        )

    def test_ceo_cannot_create_payroll_summary(self):
        with self.assertRaises(PermissionDenied):
            create_payroll_summary(
                self.ceo,
                self.start,
                self.end,
            )

        self.assertEqual(PayrollSummary.objects.count(), 0)

    def test_sales_manager_cannot_create_payroll_summary(self):
        with self.assertRaises(PermissionDenied):
            create_payroll_summary(
                self.sales_manager,
                self.start,
                self.end,
            )

        self.assertEqual(PayrollSummary.objects.count(), 0)

    def test_ceo_cannot_approve_payroll_summary(self):
        summary = self.draft()

        with self.assertRaises(PermissionDenied):
            approve_payroll_summary(
                self.ceo,
                summary.pk,
            )

        summary.refresh_from_db()
        self.assertEqual(summary.status, PayrollSummary.Status.DRAFT)
        self.assertIsNone(summary.approved_at)

    def test_inactive_comptroller_cannot_create_summary(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            create_payroll_summary(
                self.comptroller,
                self.start,
                self.end,
            )

        self.assertEqual(PayrollSummary.objects.count(), 0)

    def test_inactive_comptroller_cannot_approve_summary(self):
        summary = self.draft()

        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            approve_payroll_summary(
                self.comptroller,
                summary.pk,
            )

        summary.refresh_from_db()
        self.assertEqual(summary.status, PayrollSummary.Status.DRAFT)

    def test_stale_comptroller_role_cannot_create_summary(self):
        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.SALES_MANAGER,
        )

        with self.assertRaises(PermissionDenied):
            create_payroll_summary(
                self.comptroller,
                self.start,
                self.end,
            )

        self.assertEqual(PayrollSummary.objects.count(), 0)

    def test_stale_comptroller_role_cannot_approve_summary(self):
        summary = self.draft()

        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.SALES_MANAGER,
        )

        with self.assertRaises(PermissionDenied):
            approve_payroll_summary(
                self.comptroller,
                summary.pk,
            )

        summary.refresh_from_db()
        self.assertEqual(summary.status, PayrollSummary.Status.DRAFT)

    def test_missing_actor_cannot_create_summary(self):
        with self.assertRaises(PermissionDenied):
            create_payroll_summary(
                None,
                self.start,
                self.end,
            )

        self.assertEqual(PayrollSummary.objects.count(), 0)

    def test_missing_actor_cannot_approve_summary(self):
        summary = self.draft()

        with self.assertRaises(PermissionDenied):
            approve_payroll_summary(None, summary.pk)

        summary.refresh_from_db()
        self.assertEqual(summary.status, PayrollSummary.Status.DRAFT)