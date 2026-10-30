"""Pure compensation-period overlap policy.

A payment period overlaps a selected report range when both
periods share at least one calendar day.

This module does not authorize access or query compensation records.
"""

from datetime import date

from .individual_compensation_report_dates import (
    validate_individual_report_dates,
)


def compensation_period_overlaps(
    payment_start,
    payment_end,
    report_start,
    report_end,
):
    """Return whether two inclusive calendar periods overlap."""

    payment_start, payment_end = validate_individual_report_dates(
        payment_start,
        payment_end,
    )

    report_start, report_end = validate_individual_report_dates(
        report_start,
        report_end,
    )

    return (
        payment_start <= report_end
        and payment_end >= report_start
    )


def compensation_period_filter_bounds(report_start, report_end):
    """Validate and return bounds for an overlapping-period query.

    A later Django queryset can use:
        period_start__lte=end
        period_end__gte=start

    Authorization must be applied before these bounds are used.
    """

    start, end = validate_individual_report_dates(
        report_start,
        report_end,
    )

    return {
        "period_start_on_or_before": end,
        "period_end_on_or_after": start,
    }