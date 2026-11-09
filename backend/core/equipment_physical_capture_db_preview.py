"""Unregistered, read-only current-MSR physical capture assessment.

Caller-provided capture details are NOT trusted physical evidence.
No writes, approval, operational installation start, or API registration.
"""
from uuid import UUID

from .equipment_physical_capture_candidate import (
    PhysicalCaptureCandidate,
    assess_physical_capture_candidate,
)
from .equipment_physical_units import physical_units_from_snapshot
from .models import Project


def preview_current_msr_physical_capture(
    *, project_id, msr_id, unit_id, serial_number,
    recorder_id, recorder_role, recorder_active,
    captured_at, installation_starts_at,
):
    try:
        requested_project = str(UUID(str(project_id)))
        requested_msr = str(UUID(str(msr_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Valid project and MSR identifiers required.") from None

    def blocked(message):
        return PhysicalCaptureCandidate(
            msr_id=requested_msr,
            unit_id=unit_id if type(unit_id) is str else "",
            normalized_serial="",
            candidate_valid=False,
            blockers=(message,),
        )

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=requested_project).first()

    if project is None:
        return blocked("Project does not exist.")

    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or str(msr.pk) != requested_msr
        or str(msr.project_id) != requested_project
    ):
        return blocked("Current approved MSR does not match.")

    try:
        units = physical_units_from_snapshot(
            msr_id=requested_msr,
            snapshot=msr.snapshot,
        )
    except (TypeError, ValueError):
        return blocked("Approved equipment snapshot is invalid.")

    return assess_physical_capture_candidate(
        msr_id=requested_msr,
        unit_id=unit_id,
        expected_unit_ids=tuple(item.unit_id for item in units),
        serial_number=serial_number,
        recorder_id=recorder_id,
        recorder_role=recorder_role,
        recorder_active=recorder_active,
        captured_at=captured_at,
        installation_starts_at=installation_starts_at,
    )