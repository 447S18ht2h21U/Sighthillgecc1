from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    ProjectTechnicalAssignment,
    Role,
)


@transaction.atomic
def create_technical_assignment(
    actor,
    project,
    technical_associate,
    effective_date,
):

    if actor.role not in [
        Role.INSTALLATION_MANAGER,
        Role.COMPTROLLER,
    ]:
        raise ValidationError(
            'Only installation managers or comptrollers may assign technical associates.'
        )

    if technical_associate.role != Role.TECHNICIAN:
        raise ValidationError(
            'Assigned user must have the technician role.'
        )

    assignment = ProjectTechnicalAssignment.objects.create(
        project=project,
        technical_associate=technical_associate,
        assigned_by=actor,
        effective_date=effective_date,
        status=ProjectTechnicalAssignment.Status.ACTIVE,
    )

    return assignment

@transaction.atomic
def end_technical_assignment(
    actor,
    assignment_id,
):

    assignment = (
        ProjectTechnicalAssignment.objects
        .select_for_update()
        .get(pk=assignment_id)
    )

    if assignment.status != ProjectTechnicalAssignment.Status.ACTIVE:
        raise ValidationError(
            'Only active technical assignments may be ended.'
        )

    assignment.status = ProjectTechnicalAssignment.Status.ENDED
    assignment.ended_at = timezone.now()

    assignment.save(
        update_fields=[
            'status',
            'ended_at',
        ]
    )

    return assignment