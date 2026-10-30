"""Financial report approval authorization regression tests."""

from datetime import date

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .financial_report_services import approve_financial_report
from .models import FinancialReport, Role, User


class FinancialReportApprovalSecurityTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="financial_approval_security_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="financial_approval_security_ceo",
            password="isolated-test-only",
            role=Role.CEO,
            initials="CE",
        )
        self.sales_manager = User.objects.create_user(
            username="financial_approval_security_sales_manager",
            password="isolated-test-only",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.sales_associate = User.objects.create_user(
            username="financial_approval_security_sales_associate",
            password="isolated-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_snapshot={
                "revenue": "0.00",
                "net_income": "0.00",
            },
            created_by=self.comptroller,
        )

    def assert_remains_draft(self):
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.status,
            FinancialReport.Status.DRAFT,
        )
        self.assertIsNone(self.report.approved_by_id)
        self.assertIsNone(self.report.approved_at)

    def test_active_comptroller_can_approve(self):
        approved = approve_financial_report(
            self.comptroller,
            self.report.pk,
        )
        self.assertEqual(
            approved.status,
            FinancialReport.Status.APPROVED,
        )
        self.assertEqual(
            approved.approved_by_id,
            self.comptroller.pk,
        )

    def test_ceo_cannot_approve(self):
        with self.assertRaises(PermissionDenied):
            approve_financial_report(self.ceo, self.report.pk)
        self.assert_remains_draft()

    def test_sales_manager_cannot_approve(self):
        with self.assertRaises(PermissionDenied):
            approve_financial_report(
                self.sales_manager,
                self.report.pk,
            )
        self.assert_remains_draft()

    def test_sales_associate_cannot_approve(self):
        with self.assertRaises(PermissionDenied):
            approve_financial_report(
                self.sales_associate,
                self.report.pk,
            )
        self.assert_remains_draft()

    def test_inactive_comptroller_cannot_approve(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            approve_financial_report(
                self.comptroller,
                self.report.pk,
            )
        self.assert_remains_draft()

    def test_stale_comptroller_role_cannot_approve(self):
        User.objects.filter(
            pk=self.comptroller.pk,
        ).update(role=Role.SALES_ASSOCIATE)

        with self.assertRaises(PermissionDenied):
            approve_financial_report(
                self.comptroller,
                self.report.pk,
            )
        self.assert_remains_draft()

    def test_missing_actor_cannot_approve(self):
        with self.assertRaises(PermissionDenied):
            approve_financial_report(None, self.report.pk)
        self.assert_remains_draft()

    def test_unsaved_actor_cannot_approve(self):
        actor = User(
            username="unsaved_financial_approver",
            role=Role.COMPTROLLER,
        )
        with self.assertRaises(PermissionDenied):
            approve_financial_report(actor, self.report.pk)
        self.assert_remains_draft()
