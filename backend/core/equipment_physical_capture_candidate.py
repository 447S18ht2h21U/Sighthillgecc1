"""Unregistered structural assessment for proposed physical serial capture.

No database writes, identity proof, physical verification, evidence trust,
exception effectiveness, scheduling approval or installation authority.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PhysicalCaptureCandidate:
    msr_id: str
    unit_id: str
    normalized_serial: str
    candidate_valid: bool
    blockers: tuple[str, ...]
    physical_verification_trusted: bool = False
    installation_authorized: bool = False


def _uuid(value):
    if type(value) is not str:
        raise ValueError("A valid identifier is required.")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        raise ValueError("A valid identifier is required.") from None


def assess_physical_capture_candidate(
    *, msr_id, unit_id, expected_unit_ids, serial_number,
    recorder_id, recorder_role, recorder_active,
    captured_at, installation_starts_at,
):
    """Check proposed values only; never accept them as verified proof."""
    msr = _uuid(msr_id)
    _uuid(recorder_id)

    if type(expected_unit_ids) not in (tuple, list):
        raise ValueError("Expected equipment units must be a sequence.")
    if (
        not expected_unit_ids
        or any(type(item) is not str or not item.strip()
               for item in expected_unit_ids)
        or len(set(expected_unit_ids)) != len(expected_unit_ids)
    ):
        raise ValueError("Expected equipment units must be unique.")

    if type(unit_id) is not str or not unit_id.strip():
        raise ValueError("A specific physical unit is required.")

    if (
        not isinstance(captured_at, datetime)
        or captured_at.utcoffset() is None
        or not isinstance(installation_starts_at, datetime)
        or installation_starts_at.utcoffset() is None
    ):
        raise ValueError("Capture and installation times need UTC offsets.")

    blockers = []
    if unit_id not in expected_unit_ids:
        blockers.append("Unit is not in the approved equipment list.")

    if recorder_role != "INSTALLATION_MANAGER" or recorder_active is not True:
        blockers.append("Active Installation Manager recorder required.")

    serial = ""
    if type(serial_number) is not str:
        blockers.append("A valid serial number is required.")
    else:
        serial = serial_number.strip().upper()
        if (
            not serial or len(serial) > 120
            or any(ord(char) < 32 or ord(char) == 127 for char in serial)
        ):
            blockers.append("A valid serial number is required.")

    if captured_at.timestamp() > installation_starts_at.timestamp():
        blockers.append("Equipment identification must precede installation.")

    return PhysicalCaptureCandidate(
        msr_id=msr,
        unit_id=unit_id,
        normalized_serial=serial,
        candidate_valid=not blockers,
        blockers=tuple(blockers),
    )