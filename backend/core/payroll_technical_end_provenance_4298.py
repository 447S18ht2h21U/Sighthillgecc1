"""Test-only assignment-ending audit provenance.

Checks persisted assignment and matching creation/ending audit events.
Does not verify the entire audit hash chain, establish compensation
attribution, or authorize any payroll disclosure.
"""
from datetime import date

from .models import AuditEvent, ProjectTechnicalAssignment, Role
from .payroll_technical_provenance_4296 import (
    _uuid,
    candidate_database_technical_role,
)


def _ending_events(assignment):
    return list(AuditEvent.objects.filter(
        entity_id=assignment.pk,
        action="TECHNICAL_ASSIGNMENT_ENDED",
    ))


def _creation_events(assignment):
    return list(AuditEvent.objects.filter(
        entity_id=assignment.pk,
        action="TECHNICAL_ASSIGNMENT_CREATED",
    ))


def _ending_consistent(assignment, creation, ending):
    if ending is None or creation is None:
        return False
    if assignment.ended_at is None:
        return False
    if type(ending.payload) is not dict:
        return False
    if type(creation.payload) is not dict:
        return False
    if ending.entity_id != assignment.pk:
        return False
    if creation.entity_id != assignment.pk:
        return False
    if ending.action != "TECHNICAL_ASSIGNMENT_ENDED":
        return False
    if creation.action != "TECHNICAL_ASSIGNMENT_CREATED":
        return False
    if not ending.actor_id or not creation.actor_id:
        return False
    if creation.actor_id != assignment.assigned_by_id:
        return False
    if ending.sequence <= creation.sequence:
        return False

    expected = {
        "project_id": str(assignment.project_id),
        "technical_associate_id": str(assignment.technical_associate_id),
        "ended_at": assignment.ended_at.isoformat(),
    }
    for key, value in expected.items():
        if ending.payload.get(key) != value:
            return False

    return True


def candidate_audited_technical_period(*, subject_id, project_id, earned_on):
    """Only classify if relevant assignment histories are consistent."""
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

    if not assignments:
        return None

    for assignment in assignments:
        creations = _creation_events(assignment)
        endings = _ending_events(assignment)

        if len(creations) != 1:
            return None

        if assignment.status == ProjectTechnicalAssignment.Status.ACTIVE:
            if assignment.ended_at is not None or endings:
                return None
        elif assignment.status == ProjectTechnicalAssignment.Status.ENDED:
            if len(endings) != 1:
                return None
            if not _ending_consistent(assignment, creations[0], endings[0]):
                return None
        else:
            return None

    return candidate_database_technical_role(
        subject_id=subject,
        project_id=project,
        earned_on=earned_on,
    )


def audited_technical_period_grants_live_access(*args, **kwargs):
    return False