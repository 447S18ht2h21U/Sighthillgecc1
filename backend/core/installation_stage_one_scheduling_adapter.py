"""Development-only adapter for the approved Stage 1 preview.

No registration, API endpoint, scheduling permission, or installation
permission is created here. Preview evidence is not operational authority.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StageOneSchedulingAssessment:
    candidate_ready: bool
    blockers: tuple[str, ...]
    scheduling_authorized: bool = False
    installation_authorized: bool = False


def assess_stage_one_scheduling_candidate(preview):
    """Classify untrusted preview results without granting authority."""
    if preview is None:
        return StageOneSchedulingAssessment(
            False, ("Stage 1 preview evidence is missing.",)
        )

    required = (
        "msr_id", "requirements_satisfied", "blockers",
        "installation_authorized",
    )
    if any(not hasattr(preview, field) for field in required):
        return StageOneSchedulingAssessment(
            False, ("Stage 1 preview evidence is incomplete.",)
        )

    if (
        not isinstance(preview.msr_id, str)
        or not preview.msr_id.strip()
        or type(preview.requirements_satisfied) is not bool
        or type(preview.installation_authorized) is not bool
        or preview.installation_authorized is not False
        or not isinstance(preview.blockers, tuple)
        or any(not isinstance(item, str) or not item for item in preview.blockers)
    ):
        return StageOneSchedulingAssessment(
            False, ("Stage 1 preview evidence failed validation.",)
        )

    if preview.requirements_satisfied and not preview.blockers:
        return StageOneSchedulingAssessment(True, ())

    return StageOneSchedulingAssessment(
        False,
        preview.blockers or ("Stage 1 requirements are incomplete.",),
    )
