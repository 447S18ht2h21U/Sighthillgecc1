"""Accounting readiness gate regression for CEO financial approval."""

from datetime import date

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from .financial_report_services import approve_financial_report
from .models import FinancialReport, Role, User


class FinancialAccountingApprovalGate4435Tests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="4435_comptroller",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        self.ceo = User.objects.create_user(
            username="4435_ceo",
            role=Role.CEO,
            initials="CE",
        )

    def make_report(self, kind, snapshot=None):
        return FinancialReport.objects.create(
            kind=kind,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_snapshot=snapshot or {
                "cash": "10000.00",
                "total_assets": "10000.00",
            },
            created_by=self.comptroller,
        )

    def assert_unchanged_draft(self, report):
        report.refresh_from_db()
        self.assertEqual(report.status, FinancialReport.Status.DRAFT)
        self.assertIsNone(report.approved_by_id)
        self.assertIsNone(report.approved_at)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_01_ceo_cannot_approve_incomplete_balance_sheet(self):
        report = self.make_report(FinancialReport.Kind.BALANCE_SHEET)

        with self.assertRaisesMessage(
            ValidationError, "independently reconciled"
        ):
            approve_financial_report(self.ceo, report.pk)

        self.assert_unchanged_draft(report)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_02_ceo_cannot_approve_incomplete_cash_flow(self):
        report = self.make_report(FinancialReport.Kind.CASH_FLOW)

        with self.assertRaisesMessage(
            ValidationError, "independently reconciled"
        ):
            approve_financial_report(self.ceo, report.pk)

        self.assert_unchanged_draft(report)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=True)
    def test_03_snapshot_claim_cannot_bypass_gate(self):
        report = self.make_report(
            FinancialReport.Kind.BALANCE_SHEET,
            {
                "accounting_reconciled": True,
                "financial_statement_ready": True,
                "total_assets": "999999.00",
            },
        )

        with self.assertRaises(ValidationError):
            approve_financial_report(self.ceo, report.pk)

        self.assert_unchanged_draft(report)

    @override_settings(VERIDIAN_CEO_FINANCIAL_APPROVAL_ENABLED=False)
    def test_04_legacy_path_remains_unchanged_when_flag_off(self):
        report = self.make_report(FinancialReport.Kind.BALANCE_SHEET)

        approved = approve_financial_report(
            self.comptroller, report.pk
        )

        self.assertEqual(
            approved.status, FinancialReport.Status.APPROVED
        )
        self.assertEqual(
            approved.approved_by_id, self.comptroller.pk
        )
