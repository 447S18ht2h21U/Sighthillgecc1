"""Pure future-date calculation; never grants installation-start authority."""

from datetime import date, datetime, time

from .installation_waiting_period_policy import EASTERN, assess_waiting_period


def assess_future_installation_date(
    *,
    proposed_date,
    verified_contract_signed_at,
    verified_cancellation_deadline,
    now,
):
    if type(proposed_date) is not date:
        raise ValueError("A valid installation calendar date is required.")

    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Current time must include a valid UTC offset.")

    current = now.astimezone(EASTERN)

    if proposed_date < current.date():
        raise ValueError("Past installation dates cannot be newly scheduled.")

    candidate_time = (
        current
        if proposed_date == current.date()
        else datetime.combine(proposed_date, time.min, tzinfo=EASTERN)
    )

    waiting = assess_waiting_period(
        verified_contract_signed_at=verified_contract_signed_at,
        verified_cancellation_deadline=verified_cancellation_deadline,
        now=candidate_time,
    )

    return {
        "normal_date_eligible": waiting.ready,
        "earliest_at": waiting.earliest_at,
        "installation_authorized": False,
        "expedited_authorized": False,
    }