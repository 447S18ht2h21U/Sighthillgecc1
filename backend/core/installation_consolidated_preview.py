"""Unregistered, read-only two-stage installation readiness preview.

Stage 1 checks pre-installation commercial requirements.
Stage 2 checks untrusted synthetic equipment identification evidence.
Neither the individual checks nor their combination grant authority.
"""
from dataclasses import dataclass
from datetime import datetime

from .installation_three_stage_preview import preview_pre_installation
from .equipment_recorded_readiness_preview import preview_recorded_equipment
from .models import Project


@dataclass(frozen=True)
class ConsolidatedInstallationPreview:
    msr_id: str | None
    stage_one_candidate: bool
    stage_two_candidate: bool
    combined_candidate: bool
    stage_one_blockers: tuple[str, ...]
    stage_two_blockers: tuple[str, ...]
    expected_physical_units: int
    recorded_serial_units: tuple[str, ...]
    exception_candidate_units: tuple[str, ...]
    trusted_installation_evidence: bool = False
    scheduling_authorized: bool = False
    installation_authorized: bool = False


def preview_consolidated_installation(
    *, project_id, installation_starts_at, now=None
):
    """Read two independent assessments; never write or authorize."""
    from uuid import UUID

    try:
        UUID(str(project_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A valid project identifier is required.") from None

    if (
        not isinstance(installation_starts_at, datetime)
        or installation_starts_at.utcoffset() is None
    ):
        raise ValueError("Installation start time must include a UTC offset.")

    if now is not None and (
        not isinstance(now, datetime) or now.utcoffset() is None
    ):
        raise ValueError("Current time must include a UTC offset.")

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_id).first()

    if project is None:
        return ConsolidatedInstallationPreview(
            msr_id=None,
            stage_one_candidate=False,
            stage_two_candidate=False,
            combined_candidate=False,
            stage_one_blockers=("Project was not found.",),
            stage_two_blockers=("Current approved MSR is required.",),
            expected_physical_units=0,
            recorded_serial_units=(),
            exception_candidate_units=(),
        )

    stage_one = preview_pre_installation(project, now=now)
    msr_id = (
        str(project.current_approved_id)
        if project.current_approved_id is not None else None
    )

    if msr_id is None:
        return ConsolidatedInstallationPreview(
            msr_id=None,
            stage_one_candidate=False,
            stage_two_candidate=False,
            combined_candidate=False,
            stage_one_blockers=tuple(stage_one.blockers),
            stage_two_blockers=("Current approved MSR is required.",),
            expected_physical_units=0,
            recorded_serial_units=(),
            exception_candidate_units=(),
        )

    stage_two = preview_recorded_equipment(
        project_id=project.pk,
        msr_id=msr_id,
        installation_starts_at=installation_starts_at,
    )

    identity_matches = (
        stage_one.msr_id == msr_id
        and stage_two.msr_id == msr_id
    )
    stage_one_blockers = list(stage_one.blockers)
    stage_two_blockers = list(stage_two.blockers)

    if not identity_matches:
        stage_one_blockers.append(
            "The two assessments do not reference the same approved MSR."
        )

    first = (
        identity_matches
        and stage_one.requirements_satisfied is True
        and not stage_one_blockers
    )
    second = (
        identity_matches
        and stage_two.candidate_complete is True
        and not stage_two_blockers
    )

    # The recorded equipment records are synthetic/untrusted.
    # A combined candidate must never become operational authority.
    return ConsolidatedInstallationPreview(
        msr_id=msr_id,
        stage_one_candidate=first,
        stage_two_candidate=second,
        combined_candidate=first and second,
        stage_one_blockers=tuple(stage_one_blockers),
        stage_two_blockers=tuple(stage_two_blockers),
        expected_physical_units=stage_two.expected_units,
        recorded_serial_units=stage_two.serial_units,
        exception_candidate_units=stage_two.exception_candidate_units,
    )