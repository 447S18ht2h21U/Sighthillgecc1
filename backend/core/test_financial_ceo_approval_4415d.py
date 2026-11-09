"""Default-off, isolated CEO corporate financial approval tests."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from .financial_report_services import approve_financial_report
from .financial_reporting_api import (
    financial_report_detail, financial_report_approve,
    financial_reports,
)
from .models import FinancialReport, Role, User


class CEOFinancialApproval4415DTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="4415d_comptroller",
            password="isolated-test-only",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="4415d_ceo",
            password="isolated-test-only",
            role=Role.CEO,
            initials="CE",
        )
        self.report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_snapshot={
                "revenue": "100.00",
                "net_income": "100.00",
            },
            created_by=self.comptroller,
        )

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_01_ceo_approves_comptroller_draft(self):
        report = approve_financial_report(self.ceo, self.report.pk)
        self.assertEqual(report.status, FinancialReport.Status.APPROVED)
        self.assertEqual(report.approved_by_id, self.ceo.pk)
        self.assertEqual(report.created_by_id, self.comptroller.pk)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_02_comptroller_cannot_finally_approve(self):
        with self.assertRaises(PermissionDenied):
            approve_financial_report(self.comptroller, self.report.pk)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, FinancialReport.Status.DRAFT)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_03_ceo_cannot_approve_own_draft(self):
        self.report.created_by = self.ceo
        self.report.save(update_fields=["created_by"])
        with self.assertRaises(ValidationError):
            approve_financial_report(self.ceo, self.report.pk)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, FinancialReport.Status.DRAFT)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_04_ceo_api_can_read_and_approve(self):
        factory = APIRequestFactory()
        read = factory.get("/api/financial-reports/test/")
        force_authenticate(read, user=self.ceo)
        result = financial_report_detail(read, report_id=self.report.pk)
        self.assertEqual(result.status_code, 200)

        request = factory.post(
            "/api/financial-reports/test/approve/", {}, format="json"
        )
        force_authenticate(request, user=self.ceo)
        result = financial_report_approve(
            request, report_id=self.report.pk
        )
        self.assertEqual(result.status_code, 200)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_05_ceo_cannot_create_report(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/financial-reports/", {}, format="json"
        )
        force_authenticate(request, user=self.ceo)
        response = financial_reports(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_06_audit_failure_rolls_back(self):
        with patch(
            "core.financial_report_services.audit",
            side_effect=RuntimeError("Isolated audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Isolated audit failure"
            ):
                approve_financial_report(self.ceo, self.report.pk)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, FinancialReport.Status.DRAFT)
        self.assertIsNone(self.report.approved_by_id)
        self.assertIsNone(self.report.approved_at)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=False)
    def test_07_flag_off_denies_ceo(self):
        with self.assertRaises(PermissionDenied):
            approve_financial_report(self.ceo, self.report.pk)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, FinancialReport.Status.DRAFT)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_08_duplicate_approval_rejected(self):
        approve_financial_report(self.ceo, self.report.pk)
        with self.assertRaises(ValidationError):
            approve_financial_report(self.ceo, self.report.pk)
