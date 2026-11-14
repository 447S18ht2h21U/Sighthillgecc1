"""Read-only physical inspection candidate correlation.

This is NOT post-installation acceptance or trusted installation evidence.
"""
from dataclasses import dataclass

from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_inspection_verifier import (
    verify_physical_inspection_candidate,
)


@dataclass(frozen=True)
class InstallationInspectionCorrelation:
    project_id: str
    msr_id: str
    physical_unit_count: int
    verified_candidate_count: int
    all_candidates_verified: bool
    blockers: tuple[str, ...]
    post_installation_acceptance_verified: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def assess_installation_inspection_candidates(project):
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or project.state == "CANCELLED"
        or type(msr.snapshot) is not dict
    ):
        raise ValueError("Current approved project evidence required.")

    pid, mid = str(project.pk), str(msr.pk)
    blockers = []
    try:
        units = tuple(physical_units_from_snapshot(
            msr_id=mid, snapshot=msr.snapshot
        ))
        ids = [unit.unit_id for unit in units]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Missing or duplicate physical units.")
    except (ValueError, TypeError, AttributeError):
        units = ()
        blockers.append("Approved physical-unit inventory is invalid.")

    verified = 0
    for unit in units:
        try:
            result = verify_physical_inspection_candidate(
                project_id=pid, msr_id=mid, unit_id=unit.unit_id
            )
            valid = (
                result.msr_id == mid
                and result.unit_id == unit.unit_id
                and result.review_candidate_verified is True
                and result.trusted_installation_evidence is False
                and result.installation_authorized is False
            )
        except (ValueError, TypeError, AttributeError):
            valid = False

        if valid:
            verified += 1
        else:
            blockers.append(
                "Physical-unit inspection candidate not verified: "
                + unit.unit_id
            )

    blockers.append(
        "Independent post-installation inspection and acceptance "
        "have not been authenticated."
    )

    return InstallationInspectionCorrelation(
        project_id=pid,
        msr_id=mid,
        physical_unit_count=len(units),
        verified_candidate_count=verified,
        all_candidates_verified=bool(units) and verified == len(units),
        blockers=tuple(blockers),
    )
