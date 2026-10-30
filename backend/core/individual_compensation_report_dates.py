"""Calendar date validation for individual compensation reports.

Pure validation only. No database reads, writes, permission grants,
payment operations, report generation, or API integration.
"""

from datetime import date, datetime

from rest_framework.exceptions import ValidationError


def _require_calendar_date(value, label):
    """Accept an exact ISO calendar date, never a timestamp."""

    if isinstance(value, datetime):
        raise ValidationError(
            f"{label} must be a calendar date, not a timestamp."
        )

    if isinstance(value, date):
        return value

    if (
        not isinstance(value, str)
        or len(value) != 10
        or value[4:5] != "-"
        or value[7:8] != "-"
        or not (
            value[:4].isascii()
            and value[5:7].isascii()
            and value[8:].isascii()
            and value[:4].isdigit()
            and value[5:7].isdigit()
            and value[8:].isdigit()
        )
    ):
        raise ValidationError(
            f"{label} must use YYYY-MM-DD format."
        )

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            f"{label} is not a valid calendar date."
        ) from exc


def validate_individual_report_dates(start_date, end_date):
    """Return an inclusive, validated calendar date range."""

    start = _require_calendar_date(start_date, "Start date")
    end = _require_calendar_date(end_date, "End date")

    if end < start:
        raise ValidationError(
            "Report end date cannot be before start date."
        )

    return start, end