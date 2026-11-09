"""Unregistered installation-start policy design.

An existing InstallationSchedule is not proof that installation began.
Synthetic equipment evidence is never sufficient to authorize a start.
This module does not write records, transition schedules, or grant authority.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class InstallationStartReview:
    schedule_exists: bool
    stage_one_candidate: bool
    stage_two_candidate: bool
    blockers: tuple[str, ...]
    ready_to_start: bool = False
    start_authorized: bool = False
    installation_started: bool = False


def preview_installation_start(
    *,
    schedule_status,
    stage_one_candidate,
    stage_two_candidate,
    trusted_equipment_evidence=False,
):
    blockers = []
    valid_bool = (
        type(stage_one_candidate) is bool
        and type(stage_two_candidate) is bool
        and type(trusted_equipment_evidence) is bool
    )
    if not valid_bool:
        blockers.append("Invalid installation-start assessment inputs.")

    scheduled = schedule_status == "SCHEDULED"
    if not scheduled:
        blockers.append("An active scheduled installation is required.")

    if valid_bool:
        if not stage_one_candidate:
            blockers.append("Stage 1 requirements are incomplete.")
        if not stage_two_candidate:
            blockers.append("Stage 2 equipment identification is incomplete.")
        if not trusted_equipment_evidence:
            blockers.append("Trusted equipment evidence is not available.")

    # Trust is not established merely by passing a boolean argument.
    # This prototype has no verified evidence issuer or operational transition.
    blockers.append("Operational installation-start authority is not implemented.")

    return InstallationStartReview(
        schedule_exists=scheduled,
        stage_one_candidate=stage_one_candidate is True,
        stage_two_candidate=stage_two_candidate is True,
        blockers=tuple(blockers),
    )
