"""Controlled calendar-based creation of corporate financial statements.

This service does not change existing financial calculations or models.
Official corporate reporting periods are derived from the approved
calendar reporting policy rather than manually supplied dates.
"""

from rest_framework.exceptions import ValidationError

from .financial_reporting_calendar import (
    get_corporate_reporting_period,
)
from .financial_report_services import (
    create_income_statement,
    create_balance_sheet,
    create_cash_flow_statement,
)
from .models import FinancialReport
from .financial_reporting_authorization import (
    require_financial_reporting_role,
)
from .models import Role


CORPORATE_REPORT_KINDS = frozenset({
    FinancialReport.Kind.INCOME_STATEMENT,
    FinancialReport.Kind.BALANCE_SHEET,
    FinancialReport.Kind.CASH_FLOW,
})


def create_corporate_financial_report(
    actor,
    report_kind,
    frequency,
    year,
    period_number=None,
):
    """Create an official report for one calendar reporting period.

    Monthly periods require month 1-12.
    Quarterly periods require quarter 1-4.
    Annual periods cover January 1 through December 31.

    Balance Sheets use the selected period-end date.
    Project Profitability Reports are intentionally excluded.
    """

    actor = require_financial_reporting_role(
        actor, Role.COMPTROLLER
    )

    if report_kind not in CORPORATE_REPORT_KINDS:
        raise ValidationError(
            "Unsupported corporate financial report type."
        )

    try:
        period = get_corporate_reporting_period(
            frequency,
            year,
            period_number,
        )
    except ValueError as error:
        raise ValidationError(str(error)) from error

    if report_kind == FinancialReport.Kind.INCOME_STATEMENT:
        return create_income_statement(
            actor,
            period.start_date,
            period.end_date,
        )

    if report_kind == FinancialReport.Kind.CASH_FLOW:
        return create_cash_flow_statement(
            actor,
            period.start_date,
            period.end_date,
        )

    return create_balance_sheet(
        actor,
        period.balance_sheet_date,
    )
