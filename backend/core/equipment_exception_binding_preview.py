"""Unregistered, read-only equipment/exception evidence binding preview.

A verified candidate is not an effective exception and never grants
installation, scheduling, release, or document delivery authority.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .equipment_identification_preflight import preview_equipment_identification
from .equipment_serial_exception_verifier import verify_serial_exception_candidate
from .equipment_serial_exception_service import DECISION_KIND
from .models import Project, ProjectEvidence


EXCEPTION_BLOCKER = "Serial exception needs independent Comptroller approval."


@dataclass(frozen=True)
class EquipmentBindingPreview:
    msr_id: str
    expected_units: int
    verified_exception_units: tuple[str, ...]
    blockers: tuple[str, ...]
    candidate_complete: bool
    exception_effective: bool = False
    installation_authorized: bool = False


def preview_equipment_exception_binding(
    *, project_id, msr_id, records, installation_starts_at
):
    """Inspect database-backed approval candidates, without writing."""
    try:
        expected_msr = str(UUID(str(msr_id)))
        UUID(str(project_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Valid project and MSR identifiers are required.") from None

    if (
        not isinstance(installation_starts_at, datetime)
        or installation_starts_at.utcoffset() is None
    ):
        raise ValueError("Installation start requires a UTC offset.")

    if not isinstance(records, (list, tuple)):
        raise ValueError("Physical-unit evidence must be a sequence.")

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
        return EquipmentBindingPreview(
            msr_id=expected_msr,
            expected_units=0,
            verified_exception_units=(),
            blockers=("Current approved MSR is required.",),
            candidate_complete=False,
        )

    msr = project.current_approved
    base = preview_equipment_identification(
        msr_id=expected_msr,
        snapshot=msr.snapshot,
        records=records,
        installation_starts_at=installation_starts_at,
    )
    blockers = [
        item for item in base.blockers if item != EXCEPTION_BLOCKER
    ]
    verified = []
    seen_decisions = set()

    claimed_records = [
        item for item in records
        if type(item) is dict
        and type(item.get("exception_reference")) is str
        and item["exception_reference"].strip()
    ]

    for record in claimed_records:
        unit = record.get("unit_id")
        reference = record["exception_reference"].strip()

        try:
            decision_uuid = str(UUID(reference))
        except (ValueError, TypeError, AttributeError):
            blockers.append("Exception requires a real decision identifier.")
            continue

        if decision_uuid in seen_decisions:
            blockers.append("One decision cannot cover multiple units.")
            continue
        seen_decisions.add(decision_uuid)

        decision = ProjectEvidence.objects.filter(
            pk=decision_uuid, msr=msr, kind=DECISION_KIND
        ).first()
        if (
            decision is None
            or decision.data.get("unit_id") != unit
        ):
            blockers.append("Exception decision does not match this unit and MSR.")
            continue

        candidate = verify_serial_exception_candidate(
            project_id=project.pk,
            msr_id=msr.pk,
            unit_id=unit,
        )
        if not candidate.approval_candidate_verified:
            blockers.append("Independent Comptroller decision is not valid.")
            continue

        try:
            request = ProjectEvidence.objects.get(
                pk=decision.data["request_id"],
                msr=msr,
            )
        except (ProjectEvidence.DoesNotExist, ValueError, TypeError, KeyError):
            blockers.append("Original exception request is missing.")
            continue

        if (
            request.created_at > installation_starts_at
            or decision.created_at > installation_starts_at
            or request.created_at > decision.created_at
        ):
            blockers.append("Exception approval must precede installation.")
            continue

        verified.append(unit)

    if len(verified) != len(claimed_records):
        blockers.append("Not every claimed exception is verified.")

    return EquipmentBindingPreview(
        msr_id=expected_msr,
        expected_units=base.expected_units,
        verified_exception_units=tuple(sorted(set(verified))),
        blockers=tuple(blockers),
        candidate_complete=not blockers,
    )