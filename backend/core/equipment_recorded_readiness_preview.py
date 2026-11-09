"""Unregistered read-only preview of recorded equipment evidence.

Development prototype only. Synthetic records and verified exception
candidates never become trusted installation evidence through this adapter.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_serial_capture_service import SERIAL_KIND
from .equipment_serial_exception_service import DECISION_KIND
from .equipment_exception_binding_preview import (
    preview_equipment_exception_binding,
)
from .models import Project, ProjectEvidence


@dataclass(frozen=True)
class RecordedEquipmentPreview:
    msr_id: str
    expected_units: int
    serial_units: tuple[str, ...]
    exception_candidate_units: tuple[str, ...]
    blockers: tuple[str, ...]
    candidate_complete: bool
    trusted_installation_evidence: bool = False
    installation_authorized: bool = False


def preview_recorded_equipment(*, project_id, msr_id, installation_starts_at):
    """Read immutable evidence; never write, approve, or authorize."""
    try:
        expected_msr = str(UUID(str(msr_id)))
        UUID(str(project_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Valid project and MSR identifiers are required.") from None

    if (
        not isinstance(installation_starts_at, datetime)
        or installation_starts_at.utcoffset() is None
    ):
        raise ValueError("An installation start with UTC offset is required.")

    def blocked(message, count=0):
        return RecordedEquipmentPreview(
            msr_id=expected_msr,
            expected_units=count,
            serial_units=(),
            exception_candidate_units=(),
            blockers=(message,),
            candidate_complete=False,
        )

    project = Project.objects.select_related("current_approved").filter(
        pk=project_id
    ).first()
    if (
        project is None
        or project.state == "CANCELLED"
        or project.current_approved is None
        or project.current_approved.status != "APPROVED"
        or str(project.current_approved_id) != expected_msr
    ):
        return blocked("The current approved MSR does not match.")

    msr = project.current_approved
    try:
        units = physical_units_from_snapshot(
            msr_id=expected_msr, snapshot=msr.snapshot
        )
    except ValueError:
        return blocked("The approved equipment snapshot is not supported.")

    expected_ids = {unit.unit_id for unit in units}
    snapshot_digest = canonical_hash(msr.snapshot)
    records = []
    serial_units = []

    captures = list(ProjectEvidence.objects.filter(
        msr=msr, kind=SERIAL_KIND
    ).order_by("created_at", "id"))

    for evidence in captures:
        data = evidence.data
        if (
            type(data) is not dict
            or evidence.digest != canonical_hash(data)
            or data.get("purpose") != "SYNTHETIC_SERIAL_CAPTURE"
            or data.get("msr_id") != expected_msr
            or data.get("msr_version") != msr.number
            or data.get("snapshot_sha256") != snapshot_digest
            or data.get("recorded_by") != str(evidence.created_by_id)
            or data.get("trusted_installation_evidence") is not False
            or data.get("installation_authorized") is not False
            or data.get("unit_id") not in expected_ids
            or type(data.get("serial_number")) is not str
        ):
            return blocked("Serial capture evidence failed integrity review.", len(units))

        try:
            recorded_at = datetime.fromisoformat(data["recorded_at"])
        except (KeyError, TypeError, ValueError):
            return blocked("Serial capture time is invalid.", len(units))

        if (
            recorded_at.utcoffset() is None
            or recorded_at > installation_starts_at
            or evidence.created_at > installation_starts_at
            or abs((recorded_at - evidence.created_at).total_seconds()) > 120
        ):
            return blocked("Serial capture time is not verified.", len(units))

        records.append({
            "msr_id": expected_msr,
            "unit_id": data["unit_id"],
            "serial_number": data["serial_number"],
            "exception_reference": "",
            "recorded_at": recorded_at,
        })
        serial_units.append(data["unit_id"])

    decisions = list(ProjectEvidence.objects.filter(
        msr=msr, kind=DECISION_KIND
    ).order_by("created_at", "id"))

    # Never infer an approval from a request or claim. Every decision is
    # examined by the independent binding verifier below.
    for evidence in decisions:
        data = evidence.data
        if type(data) is not dict:
            return blocked("Exception decision structure is invalid.", len(units))
        unit_id = data.get("unit_id")
        if unit_id not in expected_ids:
            return blocked("Decision references unknown equipment.", len(units))

        if data.get("status") == "APPROVED":
            records.append({
                "msr_id": expected_msr,
                "unit_id": unit_id,
                "serial_number": "",
                "exception_reference": str(evidence.pk),
                "recorded_at": evidence.created_at,
            })

    result = preview_equipment_exception_binding(
        project_id=project.pk,
        msr_id=msr.pk,
        records=records,
        installation_starts_at=installation_starts_at,
    )

    return RecordedEquipmentPreview(
        msr_id=expected_msr,
        expected_units=result.expected_units,
        serial_units=tuple(sorted(set(serial_units))),
        exception_candidate_units=result.verified_exception_units,
        blockers=result.blockers,
        candidate_complete=result.candidate_complete,
    )