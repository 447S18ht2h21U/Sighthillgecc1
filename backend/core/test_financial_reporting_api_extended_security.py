"""Additional financial API authorization and input security tests."""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .financial_reporting_api import (
    financial_reports,
    financial_report_detail,
    financial_report_approve,
)
from .models import FinancialReport, Role, User


class FinancialReportingAPIExtendedSecurityTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.comptroller = User.objects.create_user(
            username="extended_api_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="extended_api_ceo",
            password="isolated-test-only",
            role=Role.CEO,
            initials="CE",
        )
        self.report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            report_snapshot={"revenue": "0.00"},
            created_by=self.comptroller,
        )

    def call(self, view, method, path, actor, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(
            path,
            data=data,
            format="json",
        )
        force_authenticate(request, user=actor)
        return view(request, **kwargs)

    def valid_create_data(self):
        return {
            "report_kind": FinancialReport.Kind.CASH_FLOW,
            "frequency": "MONTHLY",
            "year": 2026,
            "period_number": 10,
        }

    def test_disabled_comptroller_cannot_list(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        response = self.call(
            financial_reports, "GET", "/api/financial-reports/",
            self.comptroller,
        )
        self.assertEqual(response.status_code, 403)

    def test_disabled_comptroller_cannot_create(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        response = self.call(
            financial_reports, "POST", "/api/financial-reports/",
            self.comptroller, self.valid_create_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(FinancialReport.objects.count(), 1)

    def test_changed_role_cannot_retrieve(self):
        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.SALES_MANAGER
        )
        response = self.call(
            financial_report_detail, "GET",
            "/api/financial-reports/detail/",
            self.comptroller, report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 403)

    def test_changed_role_cannot_approve(self):
        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.SALES_MANAGER
        )
        response = self.call(
            financial_report_approve, "POST",
            "/api/financial-reports/approve/",
            self.comptroller, report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.status, FinancialReport.Status.DRAFT
        )

    def test_ceo_cannot_create_with_extra_financial_fields(self):
        payload = self.valid_create_data()
        payload["report_snapshot"] = {"revenue": "999999.99"}
        payload["status"] = FinancialReport.Status.APPROVED
        response = self.call(
            financial_reports, "POST", "/api/financial-reports/",
            self.ceo, payload,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(FinancialReport.objects.count(), 1)

    def test_comptroller_cannot_override_snapshot(self):
        payload = self.valid_create_data()
        payload["report_snapshot"] = {"revenue": "999999.99"}
        response = self.call(
            financial_reports, "POST", "/api/financial-reports/",
            self.comptroller, payload,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FinancialReport.objects.count(), 1)

    def test_comptroller_cannot_supply_approval_evidence(self):
        payload = self.valid_create_data()
        payload["status"] = FinancialReport.Status.APPROVED
        payload["approved_by"] = str(self.comptroller.pk)
        response = self.call(
            financial_reports, "POST", "/api/financial-reports/",
            self.comptroller, payload,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FinancialReport.objects.count(), 1)

    def test_invalid_reporting_period_creates_no_report(self):
        payload = self.valid_create_data()
        payload["frequency"] = "QUARTERLY"
        payload["period_number"] = 5
        response = self.call(
            financial_reports, "POST", "/api/financial-reports/",
            self.comptroller, payload,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FinancialReport.objects.count(), 1)
