"""Nonbinding policy foundation for versioned VERIDIAN compensation.

These pure functions do not update database records, authorize approval,
calculate payroll, or replace existing compensation services.

Production integration requires separate authorization, auditing,
effective-date safeguards, and database-backed regression tests.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CompensationVersion:
    version: int
    effective_date: date
    status: str


def validate_version(version):
    """Require a positive integer version, excluding booleans."""
    return type(version) is int and version > 0


def validate_effective_date(value):
    """Require a date rather than text or a datetime."""
    return type(value) is date


def select_historical_plan(versions, as_of_date):
    """Select the approved plan applicable to a historical earning date.

    Conflicting approved effective dates fail closed. The caller must
    provide plans for one individual or one contractor engagement only.
    """
    if not validate_effective_date(as_of_date):
        raise ValueError("A valid earning date is required.")

    candidates = []
    dates_seen = set()

    for item in versions:
        if not validate_version(item.version):
            raise ValueError("Invalid compensation version.")
        if not validate_effective_date(item.effective_date):
            raise ValueError("Invalid compensation effective date.")

        if item.status != "APPROVED":
            continue

        if item.effective_date in dates_seen:
            raise ValueError("Conflicting approved effective dates.")

        dates_seen.add(item.effective_date)

        if item.effective_date <= as_of_date:
            candidates.append(item)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (item.effective_date, item.version),
    )


def requires_retroactive_review(effective_date, processed_through_date):
    """Flag changes reaching an already processed earning period.

    This check is advisory only. Live implementation must determine
    processed periods from authoritative payroll records.
    """
    if not (
        validate_effective_date(effective_date)
        and validate_effective_date(processed_through_date)
    ):
        raise ValueError("Valid dates are required.")

    return effective_date <= processed_through_date


def may_self_approve_compensation():
    """Never approve an individual's own compensation."""
    return False


def compensation_version_access_granted():
    """No live access rights are established by this policy module."""
    return False
