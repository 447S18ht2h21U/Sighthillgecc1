"""Test-only database-backed technician assignment provenance.

A candidate classification is NOT permission to view payroll.
This checks original stored assignment and audit-event consistency.
It does not validate the complete audit hash chain or link a
specific compensation payment to an assignment.

Never register this resolver as an operational API.
"""
from datetime import date
from uuid import UUID

from .models import AuditEvent, ProjectTechnicalAssignment, Role
from .payroll_historical_evidence_4292 import candidate_historical_role


def _uuid(value):
    try:
        if isinstance(value, bool):
            return None
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def candidate_database_technical_role(*, subject_id, project_id, earned_on):
    """Find exactly one consistent, audited assignment; otherwise deny."""
    subject = _uuid(subject_id)
    project = _uuid(project_id)

    if subject is None or project is None or type(earned_on) is not date:
        return None

    assignments = list(
        ProjectTechnicalAssignment.objects.filter(
            project_id=project,
            technical_associate_id=subject,
            effective_date__lte=earned_on,
        ).order_by("pk")
    )

    matching = []

    for assignment in assignments:
        if assignment.status not in (
            ProjectTechnicalAssignment.Status.ACTIVE,
            ProjectTechnicalAssignment.Status.ENDED,
        ):
            return None

        if assignment.status == ProjectTechnicalAssignment.Status.ACTIVE:
            if assignment.ended_at is not None:
                return None
            ended = None
        else:
            if assignment.ended_at is None:
                return None
            ended = assignment.ended_at.date()
            if ended < assignment.effective_date:
                return None

        if ended is not None and ended < earned_on:
            continue

        events = list(AuditEvent.objects.filter(
            entity_id=assignment.pk,
            action="TECHNICAL_ASSIGNMENT_CREATED",
        ))

        if len(events) != 1:
            return None

        event = events[0]
        payload = event.payload

        if not isinstance(payload, dict):
            return None
        if event.actor_id != assignment.assigned_by_id:
            return None
        if payload.get("project_id") != str(assignment.project_id):
            return None
        if payload.get("technical_associate_id") != str(
            assignment.technical_associate_id
        ):
            return None
        if payload.get("effective_date") != assignment.effective_date.isoformat():
            return None

        claim = {
            "source_kind": "PROJECT_TECHNICAL_ASSIGNMENT_SNAPSHOT",
            "subject_role": Role.TECHNICIAN,
            "subject_id": str(assignment.technical_associate_id),
            "project_id": str(assignment.project_id),
            "evidence_reference": str(assignment.pk),
            "effective_date": assignment.effective_date,
            "ended_date": ended,
        }

        role = candidate_historical_role(
            claim,
            subject_id=str(subject),
            project_id=str(project),
            earned_on=earned_on,
        )

        if role is None:
            return None

        matching.append(role)

    return Role.TECHNICIAN if matching == [Role.TECHNICIAN] else None


def database_technical_provenance_grants_live_access(*args, **kwargs):
    """Always deny effective manager payroll access."""
    return False