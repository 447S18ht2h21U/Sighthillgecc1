"""Unregistered, read-only equipment identification preflight.

Consumes a caller-supplied approved MSR snapshot and proposed evidence.
This adapter cannot prove the snapshot is current, verify exceptions,
write evidence, or authorize physical equipment installation.
"""
from dataclasses import dataclass

from .equipment_physical_units import physical_units_from_snapshot
from .equipment_identification_policy import assess_equipment_identification


@dataclass(frozen=True)
class EquipmentIdentificationPreflight:
    msr_id: str
    expected_units: int
    recorded_units: int
    claimed_exception_units: tuple[str, ...]
    blockers: tuple[str, ...]
    serials_structurally_complete: bool
    exceptions_independently_verified: bool = False
    installation_authorized: bool = False


def preview_equipment_identification(
    *, msr_id, snapshot, records, installation_starts_at
):
    """Report per-unit gaps; exception claims always remain unverified."""
    units = physical_units_from_snapshot(
        msr_id=msr_id, snapshot=snapshot
    )
    expected_ids = tuple(unit.unit_id for unit in units)

    assessment = assess_equipment_identification(
        msr_id=msr_id,
        expected_unit_ids=expected_ids,
        records=records,
        installation_starts_at=installation_starts_at,
    )

    claims = ()
    if isinstance(records, (list, tuple)):
        claims = tuple(sorted({
            item["unit_id"]
            for item in records
            if type(item) is dict
            and type(item.get("unit_id")) is str
            and item["unit_id"] in expected_ids
            and type(item.get("exception_reference")) is str
            and bool(item["exception_reference"].strip())
        }))

    return EquipmentIdentificationPreflight(
        msr_id=assessment.msr_id,
        expected_units=len(units),
        recorded_units=assessment.accounted_units,
        claimed_exception_units=claims,
        blockers=assessment.blockers,
        serials_structurally_complete=assessment.candidate_complete,
    )