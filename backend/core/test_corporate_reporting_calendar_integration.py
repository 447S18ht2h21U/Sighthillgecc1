"""Database-backed tests for official corporate reporting periods."""

from datetime import date

from rest_framework.exceptions import ValidationError

from .corporate_reporting_services import create_corporate_financial_report
from .models import FinancialReport
from .test_financial_reports import FinancialReportTests


class CorporateReportingIntegrationTests(FinancialReportTests):
    """Reuse proven financial fixtures and regression checks."""

    def test_monthly_income_statement_dates(self):
        report = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.INCOME_STATEMENT,
            "MONTHLY",
            2026,
            10,
        )
        self.assertEqual(report.period_start, date(2026, 10, 1))
        self.assertEqual(report.period_end, date(2026, 10, 31))

    def test_quarterly_cash_flow_dates(self):
        report = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.CASH_FLOW,
            "QUARTERLY",
            2026,
            4,
        )
        self.assertEqual(report.period_start, date(2026, 10, 1))
        self.assertEqual(report.period_end, date(2026, 12, 31))

    def test_annual_income_statement_dates(self):
        report = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.INCOME_STATEMENT,
            "ANNUAL",
            2026,
        )
        self.assertEqual(report.period_start, date(2026, 1, 1))
        self.assertEqual(report.period_end, date(2026, 12, 31))

    def test_balance_sheet_uses_month_end(self):
        report = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.BALANCE_SHEET,
            "MONTHLY",
            2026,
            2,
        )
        self.assertEqual(report.period_start, date(2026, 2, 28))
        self.assertEqual(report.period_end, date(2026, 2, 28))

    def test_balance_sheet_same_as_of_date_cannot_duplicate(self):
        create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.BALANCE_SHEET,
            "MONTHLY",
            2026,
            12,
        )
        with self.assertRaises(ValidationError):
            create_corporate_financial_report(
                self.comptroller,
                FinancialReport.Kind.BALANCE_SHEET,
                "QUARTERLY",
                2026,
                4,
            )

        self.assertEqual(
            FinancialReport.objects.filter(
                kind=FinancialReport.Kind.BALANCE_SHEET,
                period_end=date(2026, 12, 31),
            ).count(),
            1,
        )

    def test_income_statement_duplicate_calendar_period_rejected(self):
        for attempt in range(2):
            if attempt == 0:
                create_corporate_financial_report(
                    self.comptroller,
                    FinancialReport.Kind.INCOME_STATEMENT,
                    "MONTHLY",
                    2026,
                    10,
                )
            else:
                with self.assertRaises(ValidationError):
                    create_corporate_financial_report(
                        self.comptroller,
                        FinancialReport.Kind.INCOME_STATEMENT,
                        "MONTHLY",
                        2026,
                        10,
                    )

    def test_invalid_period_does_not_create_report(self):
        before = FinancialReport.objects.count()

        with self.assertRaises(ValidationError):
            create_corporate_financial_report(
                self.comptroller,
                FinancialReport.Kind.CASH_FLOW,
                "QUARTERLY",
                2026,
                5,
            )

        self.assertEqual(FinancialReport.objects.count(), before)

    def test_project_profitability_excluded_from_corporate_calendar(self):
        before = FinancialReport.objects.count()

        with self.assertRaises(ValidationError):
            create_corporate_financial_report(
                self.comptroller,
                FinancialReport.Kind.PROJECT_PROFITABILITY,
                "ANNUAL",
                2026,
            )

        self.assertEqual(FinancialReport.objects.count(), before)

    def test_distinct_monthly_and_quarterly_income_reports(self):
        monthly = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.INCOME_STATEMENT,
            "MONTHLY",
            2026,
            10,
        )

        quarterly = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.INCOME_STATEMENT,
            "QUARTERLY",
            2026,
            4,
        )

        self.assertNotEqual(monthly.pk, quarterly.pk)
        self.assertEqual(monthly.period_start, quarterly.period_start)
        self.assertNotEqual(monthly.period_end, quarterly.period_end)

    def test_annual_and_quarterly_cash_flow_are_distinct(self):
        annual = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.CASH_FLOW,
            "ANNUAL",
            2026,
        )

        quarterly = create_corporate_financial_report(
            self.comptroller,
            FinancialReport.Kind.CASH_FLOW,
            "QUARTERLY",
            2026,
            4,
        )

        self.assertNotEqual(annual.pk, quarterly.pk)
        self.assertNotEqual(annual.period_start, quarterly.period_start)
        self.assertEqual(annual.period_end, quarterly.period_end)
