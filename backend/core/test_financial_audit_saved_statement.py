"""Database-backed tests for saved monthly direct-cost audit inspection."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .financial_audit_saved_statement import inspect_saved_monthly_direct_costs
from .models import FinancialReport, ProjectCostRecord, Role, User
from .project_cost_services import COST_FIELDS
from .test_financial_reports import FinancialReportTests


class SavedStatementAuditTests(TestCase):
    """Reuse proven fixture setup without inheriting unrelated test methods."""

    def setUp(self):
        FinancialReportTests.setUp(self)

    def make_report(self):
        from .financial_report_services import create_income_statement
        return create_income_statement(
            self.comptroller,
            date(2026, 10, 1),
            date(2026, 10, 31),
        )

    def test_matching_saved_direct_costs(self):
        report = self.make_report()
        result = inspect_saved_monthly_direct_costs(self.comptroller, report.pk)
        self.assertEqual(result["amount_comparison"], "MATCHED")
        self.assertEqual(result["difference"], "0.00")
        self.assertEqual(
            Decimal(result["saved_statement_direct_costs"]),
            Decimal(result["reconstructed_direct_costs"]),
        )

    def test_category_totals_equal_reconstruction(self):
        report = self.make_report()
        result = inspect_saved_monthly_direct_costs(self.comptroller, report.pk)
        categories = result["category_totals"]
        self.assertEqual(set(categories), set(COST_FIELDS))
        self.assertEqual(
            sum(map(Decimal, categories.values()), Decimal("0.00")),
            Decimal(result["reconstructed_direct_costs"]),
        )

    def test_cost_source_references_present(self):
        report = self.make_report()
        result = inspect_saved_monthly_direct_costs(self.comptroller, report.pk)
        self.assertGreaterEqual(result["source_record_count"], 1)
        item = result["source_records"][0]
        self.assertEqual(item["project_id"], str(self.project.pk))
        self.assertEqual(item["msr_id"], str(self.msr.pk))
        self.assertEqual(item["cost_record_id"], str(self.cost_record.pk))

    def test_difference_detected_without_modifying_report(self):
        report = self.make_report()
        original_snapshot = dict(report.report_snapshot)
        original_cost = self.cost_record.material_cost

        # Test-only discrepancy: prepare a deliberately inconsistent
        # DRAFT report snapshot without modifying approved source costs.
        altered_snapshot = dict(original_snapshot)
        altered_snapshot["direct_costs"] = str(
            Decimal(original_snapshot["direct_costs"])
            - Decimal("300.00")
        )
        report.report_snapshot = altered_snapshot
        report.save(update_fields=["report_snapshot"])

        result = inspect_saved_monthly_direct_costs(
            self.comptroller, report.pk
        )

        self.assertEqual(result["amount_comparison"], "DIFFERENCE")
        self.assertEqual(Decimal(result["difference"]), Decimal("300.00"))

        report.refresh_from_db()
        self.cost_record.refresh_from_db()

        self.assertEqual(report.report_snapshot, altered_snapshot)
        self.assertEqual(self.cost_record.material_cost, original_cost)

    def test_unauthorized_role_denied(self):
        report = self.make_report()
        with self.assertRaises(PermissionDenied):
            inspect_saved_monthly_direct_costs(self.ceo, report.pk)

    def test_no_actor_denied(self):
        report = self.make_report()
        with self.assertRaises(PermissionDenied):
            inspect_saved_monthly_direct_costs(None, report.pk)

    def test_inactive_comptroller_denied(self):
        report = self.make_report()
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            inspect_saved_monthly_direct_costs(self.comptroller, report.pk)

    def test_nonmonthly_statement_rejected(self):
        report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 15),
            report_snapshot={"direct_costs": "0.00"},
            created_by=self.comptroller,
        )
        with self.assertRaises(ValidationError):
            inspect_saved_monthly_direct_costs(self.comptroller, report.pk)

    def test_balance_sheet_rejected(self):
        report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.BALANCE_SHEET,
            period_start=date(2026, 10, 31),
            period_end=date(2026, 10, 31),
            report_snapshot={"direct_costs": "0.00"},
            created_by=self.comptroller,
        )
        with self.assertRaises(ValidationError):
            inspect_saved_monthly_direct_costs(self.comptroller, report.pk)

    def test_missing_snapshot_amount_rejected(self):
        report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_snapshot={},
            created_by=self.comptroller,
        )
        with self.assertRaises(ValidationError):
            inspect_saved_monthly_direct_costs(self.comptroller, report.pk)

    def test_nonfinite_snapshot_amount_rejected(self):
        report = FinancialReport.objects.create(
            kind=FinancialReport.Kind.INCOME_STATEMENT,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_snapshot={"direct_costs": "NaN"},
            created_by=self.comptroller,
        )
        with self.assertRaises(ValidationError):
            inspect_saved_monthly_direct_costs(self.comptroller, report.pk)

    def test_audit_never_certifies_reconciliation(self):
        report = self.make_report()
        result = inspect_saved_monthly_direct_costs(self.comptroller, report.pk)
        self.assertFalse(result["financial_statement_reconciled"])
        self.assertFalse(result["historical_source_snapshot_available"])
        self.assertFalse(result["accounting_adjustment_performed"])

    def test_approved_report_remains_unchanged(self):
        from .financial_report_services import approve_financial_report
        report = self.make_report()
        approve_financial_report(self.comptroller, report.pk)
        report.refresh_from_db()
        snapshot_before = dict(report.report_snapshot)
        status_before = report.status
        inspect_saved_monthly_direct_costs(self.comptroller, report.pk)
        report.refresh_from_db()
        self.assertEqual(report.report_snapshot, snapshot_before)
        self.assertEqual(report.status, status_before)
        self.assertEqual(report.status, FinancialReport.Status.APPROVED)
