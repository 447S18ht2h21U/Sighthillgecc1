"""Extra role-security checks for default-off CEO financial approval."""

from datetime import date

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from .financial_report_services import approve_financial_report
from .financial_reporting_api import (
    financial_reports, financial_report_detail,
    financial_report_approve,
)
from .models import FinancialReport, Role, User


class FinancialCEOSecurity4416Tests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="financial_4416_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="financial_4416_ceo",
            password="isolated-test-only",
            role=Role.CEO,
            initials="CE",
        )
        self.manager = User.objects.create_user(
            username="financial_4416_manager",
            password="isolated-test-only",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            report_snapshot={"revenue": "100.00"},
            created_by=self.comptroller,
        )
        self.factory = APIRequestFactory()

    def assert_draft(self):
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.status, FinancialReport.Status.DRAFT
        )
        self.assertIsNone(self.report.approved_by_id)
        self.assertIsNone(self.report.approved_at)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_01_inactive_ceo_denied(self):
        self.ceo.is_active = False
        self.ceo.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            approve_financial_report(self.ceo, self.report.pk)
        self.assert_draft()

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_02_changed_ceo_role_denied(self):
        self.ceo.role = Role.SALES_MANAGER
        self.ceo.save(update_fields=["role"])
        with self.assertRaises(PermissionDenied):
            approve_financial_report(self.ceo, self.report.pk)
        self.assert_draft()

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_03_invalid_creator_role_denied(self):
        self.comptroller.role = Role.SALES_MANAGER
        self.comptroller.save(update_fields=["role"])
        with self.assertRaises(PermissionDenied):
            approve_financial_report(self.ceo, self.report.pk)
        self.assert_draft()

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_04_manager_cannot_approve_and_ceo_can_list(self):
        request = self.factory.post(
            "/api/financial-reports/test/approve/", {},
            format="json"
        )
        force_authenticate(request, user=self.manager)
        response = financial_report_approve(
            request, report_id=self.report.pk
        )
        self.assertEqual(response.status_code, 403)
        self.assert_draft()

        request = self.factory.get("/api/financial-reports/")
        force_authenticate(request, user=self.ceo)
        response = financial_reports(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=False)
    def test_05_default_off_ceo_api_access_denied(self):
        request = self.factory.get(
            "/api/financial-reports/test/"
        )
        force_authenticate(request, user=self.ceo)
        response = financial_report_detail(
            request, report_id=self.report.pk
        )
        self.assertEqual(response.status_code, 403)

        request = self.factory.post(
            "/api/financial-reports/test/approve/", {},
            format="json"
        )
        force_authenticate(request, user=self.ceo)
        response = financial_report_approve(
            request, report_id=self.report.pk
        )
        self.assertEqual(response.status_code, 403)
        self.assert_draft()
