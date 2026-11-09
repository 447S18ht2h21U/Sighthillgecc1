"""Unregistered waiting-period calculation for the approved Invoice workflow.

This pure function does not verify signatures, cancellation evidence,
payment, or installation authority. Callers must independently verify
those records before relying on the result.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")
WAITING_DAYS = 5


@dataclass(frozen=True)
class WaitingPeriodAssessment:
    contract_wait_ends_at: datetime
    cancellation_ends_at: datetime
    earliest_at: datetime
    ready: bool
    installation_authorized: bool = False


def _eastern(value, label):
    if not isinstance(value, datetime):
        raise ValueError(f"{label} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a UTC offset.")
    return value.astimezone(EASTERN)


def assess_waiting_period(
    *, verified_contract_signed_at, verified_cancellation_deadline,
    now,
):
    contract = _eastern(
        verified_contract_signed_at, "Contract signature"
    )
    cancellation = _eastern(
        verified_cancellation_deadline, "Cancellation deadline"
    )
    current = _eastern(now, "Current time")

    # Five local calendar days after the verified Contract signature.
    contract_wait_ends = contract + timedelta(days=WAITING_DAYS)

    # Comparing UTC instants handles different Eastern UTC offsets safely.
    earliest = max(
        (contract_wait_ends, cancellation),
        key=lambda value: value.timestamp(),
    )
    return WaitingPeriodAssessment(
        contract_wait_ends_at=contract_wait_ends,
        cancellation_ends_at=cancellation,
        earliest_at=earliest,
        ready=current.timestamp() >= earliest.timestamp(),
    )