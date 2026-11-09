"""Unregistered Stage 2 equipment identification policy.

Structural checks only. No database writes, trusted exception
verification, installation authorization, or document modification.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class EquipmentIdentificationAssessment:
    msr_id: str
    accounted_units: int
    blockers: tuple[str, ...]
    candidate_complete: bool
    exceptions_independently_verified: bool = False
    installation_authorized: bool = False


def _valid_uuid(value):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("A valid MSR identifier is required.") from None


def assess_equipment_identification(
    *, msr_id, expected_unit_ids, records, installation_starts_at
):
    """Evaluate proposed physical-unit evidence, never grant authority."""
    msr = _valid_uuid(msr_id)

    if (
        not isinstance(installation_starts_at, datetime)
        or installation_starts_at.utcoffset() is None
    ):
        raise ValueError("Installation start time must include a UTC offset.")

    if (
        not isinstance(expected_unit_ids, (tuple, list))
        or not expected_unit_ids
        or any(not isinstance(x, str) or not x.strip()
               for x in expected_unit_ids)
        or len(set(expected_unit_ids)) != len(expected_unit_ids)
    ):
        raise ValueError("Expected units must be nonempty and unique.")

    if not isinstance(records, (tuple, list)):
        raise ValueError("Equipment records must be a sequence.")

    blockers = []
    seen_units = set()
    seen_serials = set()

    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "msr_id", "unit_id", "serial_number",
            "exception_reference", "recorded_at"
        }:
            blockers.append("Invalid equipment evidence structure.")
            continue

        unit = record["unit_id"]
        if not isinstance(unit, str) or unit not in expected_unit_ids:
            blockers.append("Unknown equipment unit.")
            continue
        if unit in seen_units:
            blockers.append("Duplicate equipment unit record.")
            continue
        seen_units.add(unit)

        if record["msr_id"] != msr:
            blockers.append("Evidence belongs to another MSR.")
            continue

        recorded = record["recorded_at"]
        if (
            not isinstance(recorded, datetime)
            or recorded.utcoffset() is None
            or recorded.timestamp() > installation_starts_at.timestamp()
        ):
            blockers.append("Identification must precede installation.")
            continue

        serial = record["serial_number"]
        exception = record["exception_reference"]

        if not isinstance(serial, str) or not isinstance(exception, str):
            blockers.append("Invalid serial or exception value.")
            continue

        serial = serial.strip().upper()
        exception = exception.strip()

        if serial and exception:
            blockers.append("Serial and exception cannot both be entered.")
        elif serial:
            if serial in seen_serials:
                blockers.append("Duplicate equipment serial number.")
            else:
                seen_serials.add(serial)
        elif exception:
            blockers.append(
                "Serial exception needs independent Comptroller approval."
            )
        else:
            blockers.append("Serial number or approved exception is missing.")

    missing = set(expected_unit_ids) - seen_units
    if missing:
        blockers.append("Some physical equipment units are not accounted for.")

    return EquipmentIdentificationAssessment(
        msr_id=msr,
        accounted_units=len(seen_units),
        blockers=tuple(blockers),
        candidate_complete=not blockers,
    )