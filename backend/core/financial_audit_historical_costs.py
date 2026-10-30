"""Historical category-level project costs for financial audit review.

Pure calculations only. No database access or financial statement changes.
The caller supplies the available project cost records.
"""

from datetime import date

from .financial_audit_cost_categories import (
    summarize_project_cost_categories,
)
from .financial_audit_cost_versions import (
    select_project_cost_versions_as_of,
)


def summarize_historical_project_costs(records, cutoff_date):
    """Select eligible cost versions and calculate their category totals.

    This is an as-of cost position, not an expense-recognition calculation.
    """

    selection = select_project_cost_versions_as_of(
        records,
        cutoff_date,
    )

    summary = summarize_project_cost_categories(
        selection["selected_records"]
    )

    version_counts = selection["approved_version_counts"]

    multiple_versions = [
        project_id
        for project_id, count in version_counts.items()
        if count > 1
    ]

    return {
        "cutoff_date": selection["cutoff_date"],
        "selection_policy": selection["selection_policy"],
        "selected_record_ids": selection["selected_record_ids"],
        "selected_record_count": summary["record_count"],
        "category_totals": summary["category_totals"],
        "grand_total": summary["grand_total"],
        "records": summary["records"],
        "approved_version_counts": version_counts,
        "projects_with_multiple_approved_versions": multiple_versions,
        "reporting_basis": "HISTORICAL_PROJECT_COST_POSITION",
        "monthly_expense_recognition": "NOT_DETERMINED",
        "financial_statement_reconciled": False,
    }
