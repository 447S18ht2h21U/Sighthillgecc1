from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import (
    InstallationSchedule,
    Role,
)
from .services import audit

from django.utils import timezone

@transaction.atomic
def create_installation_schedule(
    actor,
    project,
    scheduled_date,
    installation_manager,
):
    if actor.role not in [
        Role.INSTALLATION_MANAGER,
        Role.COMPTROLLER,
    ]:
        raise ValidationError(
            'Only installation managers or comptrollers may schedule installations.'
        )

    if installation_manager.role != Role.INSTALLATION_MANAGER:
        raise ValidationError(
            'Assigned installation manager must have the installation manager role.'
        )

    schedule = InstallationSchedule.objects.create(
        project=project,
        scheduled_date=scheduled_date,
        installation_manager=installation_manager,
        scheduled_by=actor,
        status=InstallationSchedule.Status.SCHEDULED,
    )

    audit(
        actor,
        'installation_schedule.created',
        schedule.id,
        {
            'project_id': str(project.id),
            'scheduled_date': str(scheduled_date),
            'installation_manager_id': str(
                installation_manager.id
            ),
        },
    )

    return schedule

@transaction.atomic
def complete_installation_schedule(
    actor,
    schedule_id,
):
    schedule = (
        InstallationSchedule.objects
        .select_for_update()
        .get(pk=schedule_id)
    )

    if schedule.status != InstallationSchedule.Status.SCHEDULED:
        raise ValidationError(
            'Only scheduled installations may be completed.'
        )

    schedule.status = InstallationSchedule.Status.COMPLETED
    schedule.completed_at = timezone.now()

    schedule.save(
        update_fields=[
            'status',
            'completed_at',
        ]
    )

    return schedule

@transaction.atomic
def cancel_installation_schedule(
    actor,
    schedule_id,
):
    schedule = (
        InstallationSchedule.objects
        .select_for_update()
        .get(pk=schedule_id)
    )

    if schedule.status != InstallationSchedule.Status.SCHEDULED:
        raise ValidationError(
            'Only scheduled installations may be cancelled.'
        )

    schedule.status = InstallationSchedule.Status.CANCELLED
    schedule.cancelled_at = timezone.now()

    schedule.save(
        update_fields=[
            'status',
            'cancelled_at',
        ]
    )

    audit(
        actor,
        'installation_schedule.cancelled',
        schedule.id,
        {
            'project_id': str(
                schedule.project_id
            ),
        },
    )

    return schedule
    audit(
        actor,
        'installation_schedule.completed',
        schedule.id,
        {
            'project_id': str(
                schedule.project_id
            ),
        },
    )

    return schedule
