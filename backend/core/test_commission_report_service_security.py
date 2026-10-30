"""Service-boundary security tests for commission reports."""

from datetime import date

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .commission_report_services import (
    approve_commission_report,
    create_commission_report,
)
from .models import CommissionReport, Role, User


class CommissionReportServiceSecurityTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="commission_security_manager",
            password="test-password",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.associate = User.objects.create_user(
            username="commission_security_associate",
            password="test-password",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.comptroller = User.objects.create_user(
            username="commission_security_comptroller",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.start = date(2026, 10, 1)
        self.end = date(2026, 10, 15)

    def draft(self):
        return create_commission_report(
            self.manager,
            self.start,
            self.end,
        )

    def test_sales_associate_cannot_create_report(self):
        with self.assertRaises(PermissionDenied):
            create_commission_report(
                self.associate,
                self.start,
                self.end,
            )

        self.assertEqual(CommissionReport.objects.count(), 0)

    def test_comptroller_cannot_create_commission_report(self):
        with self.assertRaises(PermissionDenied):
            create_commission_report(
                self.comptroller,
                self.start,
                self.end,
            )

        self.assertEqual(CommissionReport.objects.count(), 0)

    def test_comptroller_cannot_approve_report(self):
        report = self.draft()

        with self.assertRaises(PermissionDenied):
            approve_commission_report(
                self.comptroller,
                report.pk,
            )

        report.refresh_from_db()
        self.assertEqual(report.status, CommissionReport.Status.DRAFT)
        self.assertIsNone(report.approved_at)

    def test_inactive_manager_cannot_create_report(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            create_commission_report(
                self.manager,
                self.start,
                self.end,
            )

        self.assertEqual(CommissionReport.objects.count(), 0)

    def test_inactive_manager_cannot_approve_report(self):
        report = self.draft()

        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            approve_commission_report(
                self.manager,
                report.pk,
            )

        report.refresh_from_db()
        self.assertEqual(report.status, CommissionReport.Status.DRAFT)

    def test_stale_manager_role_cannot_create_report(self):
        User.objects.filter(pk=self.manager.pk).update(
            role=Role.SALES_ASSOCIATE,
        )

        with self.assertRaises(PermissionDenied):
            create_commission_report(
                self.manager,
                self.start,
                self.end,
            )

        self.assertEqual(CommissionReport.objects.count(), 0)

    def test_stale_manager_role_cannot_approve_report(self):
        report = self.draft()

        User.objects.filter(pk=self.manager.pk).update(
            role=Role.SALES_ASSOCIATE,
        )

        with self.assertRaises(PermissionDenied):
            approve_commission_report(
                self.manager,
                report.pk,
            )

        report.refresh_from_db()
        self.assertEqual(report.status, CommissionReport.Status.DRAFT)

    def test_missing_actor_cannot_create_report(self):
        with self.assertRaises(PermissionDenied):
            create_commission_report(
                None,
                self.start,
                self.end,
            )

        self.assertEqual(CommissionReport.objects.count(), 0)

    def test_missing_actor_cannot_approve_report(self):
        report = self.draft()

        with self.assertRaises(PermissionDenied):
            approve_commission_report(None, report.pk)

        report.refresh_from_db()
        self.assertEqual(report.status, CommissionReport.Status.DRAFT)