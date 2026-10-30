"""Read-only comparison of monthly direct costs and historical cost position.

No database queries, financial statement modifications, or accounting
adjustments are performed. The caller supplies the project cost records.
"""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from .financial_reporting_calendar import get_corporate_reporting_period
from .financial_audit_cost_categories import summarize_project_cost_categories
from .financial_audit_historical_costs import summarize_historical_project_costs
from .project_cost_services import COST_FIELDS


EASTERN = ZoneInfo("America/New_York")
ZERO = Decimal("0.00")


def compare_monthly_direct_costs(records, year, month):
    """Compare the existing statement inclusion basis with costs as of month-end.

    Statement basis: all approved cost records approved during the month.
    Historical position: one eligible approved version per project at cutoff.
    Differences are informational; they are not accounting adjustments.
    """

    period = get_corporate_reporting_period("MONTHLY", year, month)
    records = list(records)

    monthly = []

    for record in records:
        if record.status != "APPROVED":
            continue

        approved_at = record.approved_at

        if (
            not isinstance(approved_at, datetime)
            or approved_at.tzinfo is None
            or approved_at.utcoffset() is None
        ):
            raise ValueError(
                "Approved cost records require aware approval timestamps."
            )

        local_date = approved_at.astimezone(EASTERN).date()

        if period.start_date <= local_date <= period.end_date:
            monthly.append(record)

    statement_basis = summarize_project_cost_categories(monthly)
    historical = summarize_historical_project_costs(
        records,
        period.end_date,
    )

    differences = {
        field: str(
            Decimal(historical["category_totals"][field])
            - Decimal(statement_basis["category_totals"][field])
        )
        for field in COST_FIELDS
    }

    total_difference = (
        Decimal(historical["grand_total"])
        - Decimal(statement_basis["grand_total"])
    )

    return {
        "year": period.year,
        "month": period.period_number,
        "period_start": period.start_date.isoformat(),
        "period_end": period.end_date.isoformat(),
        "statement_basis": {
            "description": "ALL_APPROVED_COST_RECORDS_DURING_MONTH",
            "category_totals": statement_basis["category_totals"],
            "grand_total": statement_basis["grand_total"],
            "record_count": statement_basis["record_count"],
            "records": statement_basis["records"],
        },
        "historical_position": historical,
        "category_differences": differences,
        "total_difference": str(total_difference),
        "projects_with_multiple_approved_versions": historical[
            "projects_with_multiple_approved_versions"
        ],
        "difference_basis": "HISTORICAL_POSITION_MINUS_MONTHLY_APPROVALS",
        "accounting_adjustment_performed": False,
        "financial_statement_reconciled": False,
    }
