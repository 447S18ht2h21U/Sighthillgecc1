"""Unregistered, fail-closed serial exception review policy.

A structural review never approves an exception. Only an independently
authorized, audited database service may later record a decision.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SerialExceptionReview:
    msr_id: str
    unit_id: str
    candidate_valid: bool
    blockers: tuple[str, ...]
    comptroller_approval_verified: bool = False
    exception_effective: bool = False
    installation_authorized: bool = False


def _uuid(value):
    if type(value) is not str:
        raise ValueError("A valid identifier is required.")
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError("A valid identifier is required.") from None


def _time(value, label):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{label} must have a UTC offset.")
    return value


def review_serial_exception(
    *,
    msr_id,
    unit_id,
    expected_unit_ids,
    requester_id,
    requester_role,
    requester_active,
    comptroller_id,
    comptroller_role,
    comptroller_active,
    reason,
    genuinely_not_applicable,
    requested_at,
    reviewed_at,
):
    msr = _uuid(msr_id)
    requester = _uuid(requester_id)
    comptroller = _uuid(comptroller_id)
    request_time = _time(requested_at, "Request time")
    review_time = _time(reviewed_at, "Review time")

    if (
        type(unit_id) is not str or not unit_id
        or type(expected_unit_ids) not in (tuple, list)
        or not expected_unit_ids
        or any(type(item) is not str or not item for item in expected_unit_ids)
        or len(set(expected_unit_ids)) != len(expected_unit_ids)
    ):
        raise ValueError("Specific, unique physical unit identifiers required.")

    if type(reason) is not str:
        raise ValueError("A written exception explanation is required.")

    blockers = []

    if unit_id not in expected_unit_ids:
        blockers.append("Unit is not part of the selected MSR.")

    if requester_role != "INSTALLATION_MANAGER" or requester_active is not True:
        blockers.append("Active Installation Manager request required.")

    if comptroller_role != "COMPTROLLER" or comptroller_active is not True:
        blockers.append("Active Comptroller review required.")

    if requester == comptroller:
        blockers.append("Requester cannot review their own exception.")

    if not reason.strip() or len(reason.strip()) < 15:
        blockers.append("Specific written explanation is required.")
    elif len(reason) > 2000:
        blockers.append("Written explanation exceeds its limit.")

    if genuinely_not_applicable is not True:
        blockers.append("Non-applicability must be explicitly established.")

    if review_time.timestamp() < request_time.timestamp():
        blockers.append("Review cannot precede the request.")

    return SerialExceptionReview(
        msr_id=msr,
        unit_id=unit_id,
        candidate_valid=not blockers,
        blockers=tuple(blockers),
    )