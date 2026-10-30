"""Security tests through registered financial reporting URL routes."""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from .models import FinancialReport, Role, User


class FinancialReportingRouteSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.comptroller = User.objects.create_user(
            username="route_security_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="route_security_ceo",
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

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def detail_url(self):
        return f"/api/financial-reports/{self.report.pk}/"

    def approval_url(self):
        return f"/api/financial-reports/{self.report.pk}/approve/"

    def test_anonymous_list_denied(self):
        response = self.client.get("/api/financial-reports/")
        self.assertIn(response.status_code, (401, 403))

    def test_anonymous_detail_denied(self):
        response = self.client.get(self.detail_url())
        self.assertIn(response.status_code, (401, 403))

    def test_anonymous_approval_denied(self):
        response = self.client.post(self.approval_url(), {}, format="json")
        self.assertIn(response.status_code, (401, 403))

    def test_ceo_list_denied(self):
        self.authenticate(self.ceo)
        response = self.client.get("/api/financial-reports/")
        self.assertEqual(response.status_code, 403)

    def test_ceo_detail_denied(self):
        self.authenticate(self.ceo)
        response = self.client.get(self.detail_url())
        self.assertEqual(response.status_code, 403)

    def test_ceo_approval_denied(self):
        self.authenticate(self.ceo)
        response = self.client.post(self.approval_url(), {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.status, FinancialReport.Status.DRAFT
        )

    def test_comptroller_can_list(self):
        self.authenticate(self.comptroller)
        response = self.client.get("/api/financial-reports/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        directives = {
            value.strip().lower()
            for value in response["Cache-Control"].split(",")
        }
        self.assertIn("no-store", directives)

    def test_comptroller_can_retrieve(self):
        self.authenticate(self.comptroller)
        response = self.client.get(self.detail_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["id"]), str(self.report.pk))

    def test_disabled_comptroller_denied(self):
        self.authenticate(self.comptroller)
        User.objects.filter(pk=self.comptroller.pk).update(is_active=False)
        response = self.client.get("/api/financial-reports/")
        self.assertEqual(response.status_code, 403)

    def test_stale_comptroller_role_denied(self):
        self.authenticate(self.comptroller)
        User.objects.filter(pk=self.comptroller.pk).update(
            role=Role.SALES_MANAGER
        )
        response = self.client.get(self.detail_url())
        self.assertEqual(response.status_code, 403)

    def test_get_cannot_approve(self):
        self.authenticate(self.comptroller)
        response = self.client.get(self.approval_url())
        self.assertEqual(response.status_code, 405)

    def test_delete_cannot_remove_report(self):
        self.authenticate(self.comptroller)
        response = self.client.delete(self.detail_url())
        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            FinancialReport.objects.filter(pk=self.report.pk).exists()
        )

    def test_put_cannot_replace_report(self):
        self.authenticate(self.comptroller)
        response = self.client.put(
            self.detail_url(),
            {"report_snapshot": {"revenue": "999999.99"}},
            format="json",
        )
        self.assertEqual(response.status_code, 405)
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.report_snapshot, {"revenue": "0.00"}
        )
