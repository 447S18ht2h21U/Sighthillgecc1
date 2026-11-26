"""Maryland home improvement cancellation calendar.

References:
    Maryland Commercial Law 14-301 and 14-302.1.
    Maryland Home Improvement Commission guidance.

This module calculates a minimum cancellation deadline for a
covered home improvement transaction.

It does not establish that a transaction is covered, authenticate
signatures, verify delivery of required notices, authorize expedited
service, or authorize installation.

GECC conservatively excludes observed fixed-date holidays as well
as the named statutory holidays, pending final legal review.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


POLICY_VERSION = "MD-HOME-IMPROVEMENT-5983-V1"

EASTERN = ZoneInfo("America/New_York")

ADULT_UNDER_65 = "ADULT_UNDER_65"
AGE_65_OR_OLDER = "AGE_65_OR_OLDER"

AGE_CATEGORIES = frozenset({
    ADULT_UNDER_65,
    AGE_65_OR_OLDER,
})


def _nth_weekday(year, month, weekday, occurrence):
    first = date(year, month, 1)

    return first + timedelta(
        days=(weekday - first.weekday()) % 7
        + 7 * (occurrence - 1)
    )


def _last_monday(year, month):
    next_month = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    )

    last = next_month - timedelta(days=1)

    return last - timedelta(days=last.weekday())


def _fixed_holidays(year):
    return {
        date(year, 1, 1),
        date(year, 7, 4),
        date(year, 11, 11),
        date(year, 12, 25),
    }


def _observed_holiday(day):
    if day.weekday() == 5:
        return day - timedelta(days=1)

    if day.weekday() == 6:
        return day + timedelta(days=1)

    return day


def named_holidays(year):
    """The nine holidays named in Commercial Law 14-301."""

    return _fixed_holidays(year) | {
        _nth_weekday(year, 2, 0, 3),   # Washington's Birthday
        _last_monday(year, 5),         # Memorial Day
        _nth_weekday(year, 9, 0, 1),   # Labor Day
        _nth_weekday(year, 10, 0, 2),  # Columbus Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving Day
    }


def excluded_holidays(year):
    """Include conservative observed-date extensions."""

    days = named_holidays(year)

    for adjacent_year in (year - 1, year, year + 1):
        if not 1 <= adjacent_year <= 9999:
            continue

        for holiday in _fixed_holidays(adjacent_year):
            observed = _observed_holiday(holiday)

            if observed.year == year:
                days.add(observed)

    return days


def is_business_day(day):
    if type(day) is not date:
        raise ValueError("A calendar date is required.")

    return (
        day.weekday() != 6
        and day not in excluded_holidays(day.year)
    )


def cancellation_business_days(age_category):
    if age_category == ADULT_UNDER_65:
        return 5

    if age_category == AGE_65_OR_OLDER:
        return 7

    raise ValueError(
        "A verified customer age category is required."
    )


def calculate_cancellation_calendar(
    *,
    transaction_date,
    age_category,
):
    """Calculate the minimum deadline, excluding transaction day.

    transaction_date must be the established legal transaction date,
    not the bid date, document preparation date, or sending date.
    """

    if type(transaction_date) is not date:
        raise ValueError("A verified transaction date is required.")

    required_days = cancellation_business_days(age_category)

    counted = []
    excluded = []

    current = transaction_date

    while len(counted) < required_days:
        current += timedelta(days=1)

        if is_business_day(current):
            counted.append(current)
        else:
            excluded.append(current)

    final_cancellation_day = counted[-1]

    first_date_after_deadline = (
        final_cancellation_day + timedelta(days=1)
    )

    # Midnight at the end of the final cancellation day.
    deadline_exclusive = datetime.combine(
        first_date_after_deadline,
        time.min,
        tzinfo=EASTERN,
    )

    return {
        "policy_version": POLICY_VERSION,
        "transaction_date": transaction_date.isoformat(),
        "age_category": age_category,
        "required_business_days": required_days,
        "counted_business_days": [
            day.isoformat() for day in counted
        ],
        "excluded_dates": [
            day.isoformat() for day in excluded
        ],
        "final_cancellation_day":
            final_cancellation_day.isoformat(),
        "cancellation_deadline_exclusive":
            deadline_exclusive.isoformat(),
        "earliest_date_after_calculated_deadline":
            first_date_after_deadline.isoformat(),
        "observed_holidays_excluded": True,
        "installation_authorized": False,
    }


def date_after_established_deadlines(
    *,
    transaction_date,
    age_category,
    independently_verified_deadline,
):
    """Respect the calculated minimum and any later verified deadline.

    This is a date calculation only. Other mandatory commercial,
    payment, equipment and installation requirements remain in force.
    """

    if (
        not isinstance(independently_verified_deadline, datetime)
        or independently_verified_deadline.utcoffset() is None
    ):
        raise ValueError(
            "An independently verified, timezone-aware "
            "cancellation deadline is required."
        )

    result = calculate_cancellation_calendar(
        transaction_date=transaction_date,
        age_category=age_category,
    )

    calculated = datetime.fromisoformat(
        result["cancellation_deadline_exclusive"]
    )

    verified = independently_verified_deadline.astimezone(EASTERN)

    effective = max(calculated, verified)

    earliest = effective.date()

    # A normal installation date must be wholly after the deadline.
    if effective.time() != time.min:
        earliest += timedelta(days=1)

    result.update({
        "verified_deadline": verified.isoformat(),
        "effective_deadline": effective.isoformat(),
        "earliest_normal_installation_date": earliest.isoformat(),
    })

    return result
