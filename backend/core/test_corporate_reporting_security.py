"""Corporate financial reporting entry-point security tests."""

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .corporate_reporting_services import (
    create_corporate_financial_report,
)
from .models import FinancialReport, Role, User


class CorporateReportingSecurityTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="corporate_security_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="corporate_security_ceo",
            password="isolated-test-only",
            role=Role.CEO,
            initials="CE",
        )
        self.sales_manager = User.objects.create_user(
            username="corporate_security_sales_manager",
            password="isolated-test-only",
            role=Role.SALES_MANAGER,
            initials="SM",
        )

    def assert_denied_without_report(self, actor):
        before = FinancialReport.objects.count()

        for kind in (
            FinancialReport.Kind.INCOME_STATEMENT,
            FinancialReport.Kind.BALANCE_SHEET,
            FinancialReport.Kind.CASH_FLOW,
        ):
            with self.subTest(report_kind=kind):
                with self.assertRaises(PermissionDenied):
                    create_corporate_financial_report(
                        actor, kind, "MONTHLY", 2026, 10
                    )

                self.assertEqual(
                    FinancialReport.objects.count(),
                    before,
                )

    def test_ceo_cannot_create_corporate_reports(self):
        self.assert_denied_without_report(self.ceo)

    def test_sales_manager_cannot_create_corporate_reports(self):
        self.assert_denied_without_report(self.sales_manager)

    def test_inactive_comptroller_cannot_create_corporate_reports(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        self.assert_denied_without_report(self.comptroller)

    def test_stale_comptroller_role_cannot_create_corporate_reports(self):
        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.SALES_MANAGER
        )
        self.assert_denied_without_report(self.comptroller)

    def test_missing_actor_cannot_create_corporate_reports(self):
        self.assert_denied_without_report(None)

    def test_unsaved_actor_cannot_create_corporate_reports(self):
        actor = User(
            username="unsaved_corporate_creator",
            role=Role.COMPTROLLER,
        )
        self.assert_denied_without_report(actor)

    def test_authorization_precedes_invalid_report_type(self):
        before = FinancialReport.objects.count()

        with self.assertRaises(PermissionDenied):
            create_corporate_financial_report(
                self.ceo, "INVALID_REPORT_KIND", "MONTHLY", 2026, 10
            )

        self.assertEqual(FinancialReport.objects.count(), before)

    def test_authorization_precedes_invalid_calendar_period(self):
        before = FinancialReport.objects.count()

        with self.assertRaises(PermissionDenied):
            create_corporate_financial_report(
                self.ceo,
                FinancialReport.Kind.CASH_FLOW,
                "QUARTERLY",
                2026,
                5,
            )

        self.assertEqual(FinancialReport.objects.count(), before)
