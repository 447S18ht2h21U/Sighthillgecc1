"""Read-only financial statement direct-cost audit reconstruction.

A matching amount is not proof of complete historical reconciliation.
No database writes, approval changes, or accounting adjustments occur.
"""

from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .financial_audit_cost_categories import (
    summarize_project_cost_categories,
)
from .financial_reporting_calendar import (
    get_corporate_reporting_period,
)
from .models import (
    FinancialReport,
    ProjectCostRecord,
    Role,
    User,
)


def inspect_saved_monthly_direct_costs(actor, report_id):
    """Compare a saved monthly income statement with current source records."""

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied(
            "Only an active Comptroller may inspect financial audit detail."
        )

    if not User.objects.filter(
        pk=actor.pk,
        is_active=True,
        role=Role.COMPTROLLER,
    ).exists():
        raise PermissionDenied(
            "An active Comptroller account is required."
        )

    report = FinancialReport.objects.get(pk=report_id)

    if report.kind != FinancialReport.Kind.INCOME_STATEMENT:
        raise ValidationError(
            "Direct-cost statement audit requires an Income Statement."
        )

    period = get_corporate_reporting_period(
        "MONTHLY",
        report.period_start.year,
        report.period_start.month,
    )

    if (
        report.period_start != period.start_date
        or report.period_end != period.end_date
    ):
        raise ValidationError(
            "This audit requires an exact calendar-month statement."
        )

    snapshot = report.report_snapshot

    if not isinstance(snapshot, dict) or "direct_costs" not in snapshot:
        raise ValidationError(
            "Saved statement direct-cost evidence is missing."
        )

    try:
        saved_total = Decimal(str(snapshot["direct_costs"]))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            "Saved statement direct-cost amount is invalid."
        ) from None

    if not saved_total.is_finite():
        raise ValidationError(
            "Saved statement direct-cost amount must be finite."
        )

    records = list(
        ProjectCostRecord.objects.filter(
            status=ProjectCostRecord.Status.APPROVED,
            approved_at__date__gte=period.start_date,
            approved_at__date__lte=period.end_date,
        ).order_by("project_id", "version", "pk")
    )

    reconstruction = summarize_project_cost_categories(records)
    reconstructed_total = Decimal(reconstruction["grand_total"])

    difference = reconstructed_total - saved_total

    return {
        "report_id": str(report.pk),
        "report_kind": report.kind,
        "report_status": report.status,
        "period_start": period.start_date.isoformat(),
        "period_end": period.end_date.isoformat(),
        "saved_statement_direct_costs": str(saved_total),
        "reconstructed_direct_costs": str(reconstructed_total),
        "difference": str(difference),
        "category_totals": reconstruction["category_totals"],
        "source_record_count": reconstruction["record_count"],
        "source_records": reconstruction["records"],
        "amount_comparison": (
            "MATCHED" if difference == Decimal("0.00")
            else "DIFFERENCE"
        ),
        "source_basis": "CURRENT_APPROVED_RECORDS_BY_APPROVAL_DATE",
        "historical_source_snapshot_available": False,
        "financial_statement_reconciled": False,
        "accounting_adjustment_performed": False,
    }
