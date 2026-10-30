"""Service-level financial report creation authorization tests."""

from datetime import date

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .financial_report_services import (
    create_income_statement,
    create_balance_sheet,
    create_cash_flow_statement,
    create_project_profitability_report,
)
from .models import FinancialReport, Role, User


class FinancialReportCreationSecurityTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="financial_creation_security_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="financial_creation_security_ceo",
            password="isolated-test-only",
            role=Role.CEO,
            initials="CE",
        )
        self.sales_manager = User.objects.create_user(
            username="financial_creation_security_sales_manager",
            password="isolated-test-only",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.sales_associate = User.objects.create_user(
            username="financial_creation_security_sales_associate",
            password="isolated-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )

    def creation_cases(self):
        start = date(2026, 10, 1)
        end = date(2026, 10, 31)
        return (
            ("income", lambda actor: create_income_statement(
                actor, start, end
            )),
            ("balance", lambda actor: create_balance_sheet(
                actor, end
            )),
            ("cash", lambda actor: create_cash_flow_statement(
                actor, start, end
            )),
            ("project", lambda actor: create_project_profitability_report(
                actor, None
            )),
        )

    def assert_denied_without_report(self, actor):
        for name, operation in self.creation_cases():
            with self.subTest(report=name):
                before = FinancialReport.objects.count()
                with self.assertRaises(PermissionDenied):
                    operation(actor)
                self.assertEqual(
                    FinancialReport.objects.count(),
                    before,
                )

    def test_ceo_cannot_create_financial_reports(self):
        self.assert_denied_without_report(self.ceo)

    def test_sales_manager_cannot_create_financial_reports(self):
        self.assert_denied_without_report(self.sales_manager)

    def test_sales_associate_cannot_create_financial_reports(self):
        self.assert_denied_without_report(self.sales_associate)

    def test_inactive_comptroller_cannot_create_financial_reports(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        self.assert_denied_without_report(self.comptroller)

    def test_stale_comptroller_role_cannot_create_financial_reports(self):
        User.objects.filter(
            pk=self.comptroller.pk
        ).update(role=Role.SALES_ASSOCIATE)
        self.assert_denied_without_report(self.comptroller)

    def test_missing_actor_cannot_create_financial_reports(self):
        self.assert_denied_without_report(None)

    def test_unsaved_actor_cannot_create_financial_reports(self):
        actor = User(
            username="unsaved_financial_creator",
            role=Role.COMPTROLLER,
        )
        self.assert_denied_without_report(actor)
