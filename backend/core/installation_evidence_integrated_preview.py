"""Unregistered installation and physical-unit evidence integration preview.

Read-only aggregation of the established installation preview and
independently reviewed equipment candidates. No operational authority.
"""
from dataclasses import dataclass
from uuid import UUID

from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_inspection_verifier import (
    verify_physical_inspection_candidate,
)
from .installation_consolidated_preview import (
    preview_consolidated_installation,
)
from .models import Project


@dataclass(frozen=True)
class InstallationEvidenceIntegratedPreview:
    project_id: str
    msr_id: str
    installation_assessment: object
    unit_assessments: tuple
    total_units: int
    reviewed_candidate_units: int
    all_units_reviewed: bool
    blockers: tuple[str, ...]
    trusted_installation_evidence: bool = False
    installation_authorized: bool = False


def preview_installation_with_physical_reviews(
    *, project_id, installation_starts_at, now=None,
):
    try:
        project_key = str(UUID(str(project_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Valid project identifier required.") from None

    # No caller-provided MSR, unit inventory, or trust assertion is accepted.
    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_key).first()

    if project is None:
        raise ValueError("Project does not exist.")

    msr = project.current_approved
    blockers = []
    unit_results = []

    if project.state == "CANCELLED":
        blockers.append("Cancelled project cannot proceed.")

    if (
        msr is None
        or msr.status != "APPROVED"
        or str(msr.project_id) != project_key
    ):
        blockers.append("Current approved MSR required.")

    if blockers:
        return InstallationEvidenceIntegratedPreview(
            project_id=project_key,
            msr_id="" if msr is None else str(msr.pk),
            installation_assessment=None,
            unit_assessments=(),
            total_units=0,
            reviewed_candidate_units=0,
            all_units_reviewed=False,
            blockers=tuple(blockers),
        )

    msr_key = str(msr.pk)

    try:
        physical_units = physical_units_from_snapshot(
            msr_id=msr_key, snapshot=msr.snapshot
        )
    except (ValueError, TypeError):
        physical_units = ()
        blockers.append("Approved MSR physical-unit inventory is invalid.")

    if not physical_units:
        blockers.append("No physical units available for verification.")

    # Reuse the existing combined stage-one/stage-two assessment.
    # It remains non-operational and never grants start authority.
    existing_assessment = preview_consolidated_installation(
        project_id=project_key,
        installation_starts_at=installation_starts_at,
        now=now,
    )

    for unit in physical_units:
        check = verify_physical_inspection_candidate(
            project_id=project_key,
            msr_id=msr_key,
            unit_id=unit.unit_id,
        )
        unit_results.append(check)
        if check.review_candidate_verified is not True:
            blockers.append(
                "Unit " + unit.unit_id + ": " +
                "; ".join(check.blockers or ("Review incomplete.",))
            )

    reviewed = sum(
        result.review_candidate_verified is True
        for result in unit_results
    )
    all_reviewed = (
        len(unit_results) > 0
        and reviewed == len(unit_results)
    )

    # Even when every candidate has passed review, there is no trusted
    # operational verification or installation-start authorization.
    blockers.append(
        "Trusted installation evidence and operational start authority "
        "are not implemented."
    )

    return InstallationEvidenceIntegratedPreview(
        project_id=project_key,
        msr_id=msr_key,
        installation_assessment=existing_assessment,
        unit_assessments=tuple(unit_results),
        total_units=len(unit_results),
        reviewed_candidate_units=reviewed,
        all_units_reviewed=all_reviewed,
        blockers=tuple(blockers),
    )