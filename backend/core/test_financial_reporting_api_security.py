"""Direct-view financial API security regression tests.

Financial reporting routes remain unregistered during these tests.
"""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .financial_reporting_api import (
    financial_reports,
    financial_report_detail,
    financial_report_approve,
)
from .models import FinancialReport, Role, User


class FinancialReportingAPISecurityTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.comptroller = User.objects.create_user(
            username="financial_api_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="financial_api_ceo",
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

    def request(self, method, path, actor=None, data=None):
        request = getattr(self.factory, method.lower())(
            path,
            data=data,
            format="json",
        )
        if actor is not None:
            force_authenticate(request, user=actor)
        return request

    def test_anonymous_list_is_denied(self):
        response = financial_reports(
            self.request("GET", "/api/financial-reports/")
        )
        self.assertIn(response.status_code, (401, 403))

    def test_ceo_list_is_denied(self):
        response = financial_reports(
            self.request(
                "GET", "/api/financial-reports/", self.ceo
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_comptroller_can_list_reports(self):
        response = financial_reports(
            self.request(
                "GET", "/api/financial-reports/", self.comptroller
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["status"],
            FinancialReport.Status.DRAFT,
        )
        cache_directives = {
            directive.strip().lower()
            for directive in response["Cache-Control"].split(",")
        }
        self.assertIn("no-store", cache_directives)

    def test_comptroller_can_retrieve_report(self):
        response = financial_report_detail(
            self.request(
                "GET",
                f"/api/financial-reports/{self.report.pk}/",
                self.comptroller,
            ),
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            str(response.data["id"]),
            str(self.report.pk),
        )

    def test_ceo_cannot_retrieve_report(self):
        response = financial_report_detail(
            self.request(
                "GET",
                f"/api/financial-reports/{self.report.pk}/",
                self.ceo,
            ),
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 403)

    def test_comptroller_can_create_draft(self):
        response = financial_reports(
            self.request(
                "POST",
                "/api/financial-reports/",
                self.comptroller,
                {
                    "report_kind": FinancialReport.Kind.CASH_FLOW,
                    "frequency": "MONTHLY",
                    "year": 2026,
                    "period_number": 10,
                },
            )
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["status"],
            FinancialReport.Status.DRAFT,
        )
        self.assertEqual(FinancialReport.objects.count(), 2)

    def test_ceo_cannot_create_draft(self):
        response = financial_reports(
            self.request(
                "POST",
                "/api/financial-reports/",
                self.ceo,
                {
                    "report_kind": FinancialReport.Kind.CASH_FLOW,
                    "frequency": "MONTHLY",
                    "year": 2026,
                    "period_number": 10,
                },
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(FinancialReport.objects.count(), 1)

    def test_comptroller_can_approve_draft(self):
        response = financial_report_approve(
            self.request(
                "POST",
                f"/api/financial-reports/{self.report.pk}/approve/",
                self.comptroller,
            ),
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.status,
            FinancialReport.Status.APPROVED,
        )

    def test_ceo_cannot_approve_draft(self):
        response = financial_report_approve(
            self.request(
                "POST",
                f"/api/financial-reports/{self.report.pk}/approve/",
                self.ceo,
            ),
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.status,
            FinancialReport.Status.DRAFT,
        )

    def test_get_cannot_approve_report(self):
        response = financial_report_approve(
            self.request(
                "GET",
                f"/api/financial-reports/{self.report.pk}/approve/",
                self.comptroller,
            ),
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_cannot_remove_report(self):
        response = financial_report_detail(
            self.request(
                "DELETE",
                f"/api/financial-reports/{self.report.pk}/",
                self.comptroller,
            ),
            report_id=self.report.pk,
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            FinancialReport.objects.filter(
                pk=self.report.pk
            ).exists()
        )
