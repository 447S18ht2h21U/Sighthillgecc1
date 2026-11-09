"""Unregistered, read-only database scheduling and readiness integration.

Scheduling evidence is obtained from InstallationSchedule records.
A verified schedule never constitutes installation-start authority.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from django.utils import timezone

from .installation_unified_readiness_report import (
    preview_unified_installation_readiness,
)
from .models import InstallationSchedule, Role


EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class DatabaseScheduleAssessment:
    project_id: str
    schedule_verified: bool
    schedule_id: str | None
    scheduled_date: str | None
    blockers: tuple[str, ...]
    installation_authorized: bool = False


@dataclass(frozen=True)
class DatabaseBackedReadinessReport:
    readiness: object
    scheduling: DatabaseScheduleAssessment
    report_complete_for_review: bool
    blockers: tuple[str, ...]
    trusted_installation_evidence: bool = False
    ready_to_start: bool = False
    installation_authorized: bool = False
    installation_started: bool = False


def assess_database_schedule(*, project_id, installation_starts_at):
    try:
        project_key = str(UUID(str(project_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Valid project UUID required.") from None

    if (
        not isinstance(installation_starts_at, datetime)
        or timezone.is_naive(installation_starts_at)
    ):
        raise ValueError("Installation start must be timezone-aware.")

    expected_date = installation_starts_at.astimezone(EASTERN).date()

    def denied(reason):
        return DatabaseScheduleAssessment(
            project_id=project_key,
            schedule_verified=False,
            schedule_id=None,
            scheduled_date=None,
            blockers=(reason,),
        )

    # Read authoritative records; never accept a caller-provided status.
    rows = list(
        InstallationSchedule.objects.select_related(
            "installation_manager", "scheduled_by"
        ).filter(project_id=project_key)
    )

    active = [
        row for row in rows
        if row.status == InstallationSchedule.Status.SCHEDULED
    ]

    if len(active) != 1:
        return denied("Exactly one active scheduled installation is required.")

    row = active[0]

    if row.completed_at is not None or row.cancelled_at is not None:
        return denied("Active schedule has an inconsistent lifecycle.")

    if row.scheduled_date != expected_date:
        return denied("Scheduled date does not match installation start.")

    manager = row.installation_manager
    if (
        manager is None
        or manager.is_active is not True
        or manager.role != Role.INSTALLATION_MANAGER
    ):
        return denied("Active Installation Manager required on schedule.")

    scheduler = row.scheduled_by
    if scheduler is None or scheduler.is_active is not True:
        return denied("Scheduling account is inactive or missing.")

    return DatabaseScheduleAssessment(
        project_id=project_key,
        schedule_verified=True,
        schedule_id=str(row.pk),
        scheduled_date=expected_date.isoformat(),
        blockers=(),
    )


def preview_readiness_with_database_schedule(
    *, project_id, installation_starts_at, now=None,
):
    # The original report remains unchanged and default-deny.
    readiness = preview_unified_installation_readiness(
        project_id=project_id,
        installation_starts_at=installation_starts_at,
        now=now,
        schedule_status=None,
    )

    scheduling = assess_database_schedule(
        project_id=project_id,
        installation_starts_at=installation_starts_at,
    )

    reasons = [
        reason for reason in readiness.blockers
        if reason != "Database-verified installation schedule is required."
    ]
    reasons.extend("Scheduling: " + reason for reason in scheduling.blockers)

    # This indicates only that candidate checks are ready for review.
    # It expressly does NOT grant permission to begin installation.
    candidate_complete = (
        readiness.reviewed_candidate_complete is True
        and scheduling.schedule_verified is True
    )

    reasons.append(
        "Operational trusted-equipment evidence and installation-start "
        "authorization are not implemented."
    )

    return DatabaseBackedReadinessReport(
        readiness=readiness,
        scheduling=scheduling,
        report_complete_for_review=candidate_complete,
        blockers=tuple(dict.fromkeys(reasons)),
    )