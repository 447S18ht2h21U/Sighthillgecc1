"""Unregistered, read-only unified installation-readiness report.

Reuses existing stage-one, stage-two, physical inspection and start
policy assessments. No operational start authority. Caller-provided
schedule status is advisory and never treated as verified evidence.
"""
from dataclasses import dataclass

from .installation_evidence_integrated_preview import (
    preview_installation_with_physical_reviews,
)
from .installation_start_policy_preview import preview_installation_start


@dataclass(frozen=True)
class UnifiedReadinessReport:
    project_id: str
    msr_id: str
    stage_one_candidate: bool
    stage_two_candidate: bool
    stage_one_blockers: tuple[str, ...]
    stage_two_blockers: tuple[str, ...]
    physical_units_required: int
    physical_units_reviewed: int
    all_physical_units_reviewed: bool
    schedule_status_supplied: str | None
    schedule_verified: bool
    schedule_candidate: bool
    reviewed_candidate_complete: bool
    blockers: tuple[str, ...]
    trusted_installation_evidence: bool = False
    ready_to_start: bool = False
    installation_authorized: bool = False
    installation_started: bool = False


def preview_unified_installation_readiness(
    *, project_id, installation_starts_at, now=None,
    schedule_status=None,
):
    if schedule_status is not None and type(schedule_status) is not str:
        raise ValueError("Schedule status must be text or omitted.")

    evidence = preview_installation_with_physical_reviews(
        project_id=project_id,
        installation_starts_at=installation_starts_at,
        now=now,
    )
    base = evidence.installation_assessment

    # The existing consolidated preview computes stage one from contract,
    # payment and timing evidence. Never replace it with caller claims.
    first = (
        base is not None
        and base.stage_one_candidate is True
    )
    second = (
        base is not None
        and base.stage_two_candidate is True
    )

    first_blockers = (
        tuple(base.stage_one_blockers) if base is not None
        else ("Current approved MSR and stage-one assessment required.",)
    )
    second_blockers = (
        tuple(base.stage_two_blockers) if base is not None
        else ("Current approved MSR and stage-two assessment required.",)
    )

    # This existing policy is itself permanently default-deny. The
    # supplied schedule status is only a display hint, not a DB proof.
    start_review = preview_installation_start(
        schedule_status=schedule_status,
        stage_one_candidate=first,
        stage_two_candidate=second,
        trusted_equipment_evidence=False,
    )

    blockers = []
    blockers.extend("Stage 1: " + str(b) for b in first_blockers)
    blockers.extend("Stage 2: " + str(b) for b in second_blockers)
    blockers.extend(
        "Physical review: " + str(b) for b in evidence.blockers
        if "Trusted installation evidence and operational start authority" not in str(b)
    )
    blockers.extend(
        "Start policy: " + str(b) for b in start_review.blockers
    )

    if schedule_status is not None:
        blockers.append(
            "Schedule status is caller-supplied, not database-verified."
        )
    else:
        blockers.append("Database-verified installation schedule is required.")

    if not evidence.all_units_reviewed:
        blockers.append("All expected physical units must have accepted reviews.")

    blockers.append(
        "Trusted equipment evidence and installation-start authority "
        "are not operationally implemented."
    )

    reviewed_complete = (
        first and second
        and evidence.all_units_reviewed is True
        and evidence.total_units > 0
    )

    return UnifiedReadinessReport(
        project_id=evidence.project_id,
        msr_id=evidence.msr_id,
        stage_one_candidate=first,
        stage_two_candidate=second,
        stage_one_blockers=first_blockers,
        stage_two_blockers=second_blockers,
        physical_units_required=evidence.total_units,
        physical_units_reviewed=evidence.reviewed_candidate_units,
        all_physical_units_reviewed=evidence.all_units_reviewed is True,
        schedule_status_supplied=schedule_status,
        schedule_verified=False,
        schedule_candidate=start_review.schedule_exists is True,
        reviewed_candidate_complete=reviewed_complete,
        blockers=tuple(dict.fromkeys(blockers)),
    )