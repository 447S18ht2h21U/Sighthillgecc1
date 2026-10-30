"""Calendar periods for official VERIDIAN corporate financial reports.

Corporate financial reporting uses calendar years beginning January 1.
This module performs date calculations only; it does not access databases.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from enum import Enum


class CorporateReportingFrequency(str, Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


@dataclass(frozen=True)
class CorporateReportingPeriod:
    frequency: CorporateReportingFrequency
    year: int
    period_number: int
    start_date: date
    end_date: date

    @property
    def balance_sheet_date(self):
        """A balance sheet reports financial position as of period end."""
        return self.end_date


def get_corporate_reporting_period(
    frequency,
    year,
    period_number=None,
):
    """Return an exact calendar reporting period.

    MONTHLY requires month 1-12.
    QUARTERLY requires quarter 1-4.
    ANNUAL does not accept a period number.

    No arbitrary custom period dates are accepted here.
    """

    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("Reporting year must be an integer.")

    if not 1 <= year <= 9999:
        raise ValueError("Reporting year is outside the valid range.")

    try:
        selected_frequency = CorporateReportingFrequency(frequency)
    except (ValueError, TypeError):
        raise ValueError(
            "Reporting frequency must be MONTHLY, QUARTERLY, or ANNUAL."
        ) from None

    if selected_frequency == CorporateReportingFrequency.ANNUAL:
        if period_number is not None:
            raise ValueError(
                "Annual reporting does not accept a month or quarter."
            )

        return CorporateReportingPeriod(
            frequency=selected_frequency,
            year=year,
            period_number=1,
            start_date=date(year, 1, 1),
            end_date=date(year, 12, 31),
        )

    if (
        isinstance(period_number, bool)
        or not isinstance(period_number, int)
    ):
        raise ValueError(
            "Monthly and quarterly reports require a period number."
        )

    if selected_frequency == CorporateReportingFrequency.MONTHLY:
        if not 1 <= period_number <= 12:
            raise ValueError("Reporting month must be between 1 and 12.")

        return CorporateReportingPeriod(
            frequency=selected_frequency,
            year=year,
            period_number=period_number,
            start_date=date(year, period_number, 1),
            end_date=date(
                year,
                period_number,
                monthrange(year, period_number)[1],
            ),
        )

    if not 1 <= period_number <= 4:
        raise ValueError("Reporting quarter must be between 1 and 4.")

    first_month = (period_number - 1) * 3 + 1
    last_month = first_month + 2

    return CorporateReportingPeriod(
        frequency=selected_frequency,
        year=year,
        period_number=period_number,
        start_date=date(year, first_month, 1),
        end_date=date(
            year,
            last_month,
            monthrange(year, last_month)[1],
        ),
    )
