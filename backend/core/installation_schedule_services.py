from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import (
    InstallationSchedule,
    Role,
)
from .services import audit

from django.utils import timezone

def _authorized_installation_actor(actor):
    from rest_framework.exceptions import PermissionDenied
    from .models import User, TemporaryDutyAuthorization
    from .temporary_duty_services import is_temporary_duty_active

    message = 'An active authorized installation manager or comptroller is required.'
    if actor is None:
        raise PermissionDenied(message)

    current_actor = User.objects.filter(pk=actor.pk, is_active=True).first()
    if current_actor is None:
        raise PermissionDenied(message)

    if current_actor.role in (Role.INSTALLATION_MANAGER, Role.COMPTROLLER):
        return current_actor, None

    candidates = TemporaryDutyAuthorization.objects.filter(
        employee=current_actor,
        permanent_role=current_actor.role,
        temporary_role=Role.INSTALLATION_MANAGER,
        status=TemporaryDutyAuthorization.Status.APPROVED,
    ).order_by('-starts_at', '-pk')

    authorization = next(
        (item for item in candidates if is_temporary_duty_active(item, current_actor)),
        None,
    )
    if authorization is None:
        raise PermissionDenied('Valid temporary Installation Manager authority is required.')

    return current_actor, authorization


@transaction.atomic
def create_installation_schedule(
    actor,
    project,
    scheduled_date,
    installation_manager,
):
    current_actor, temporary_authorization = _authorized_installation_actor(actor)

    if installation_manager.role != Role.INSTALLATION_MANAGER:
        raise ValidationError(
            'Assigned installation manager must have the installation manager role.'
        )

    schedule = InstallationSchedule.objects.create(
        project=project,
        scheduled_date=scheduled_date,
        installation_manager=installation_manager,
        scheduled_by=current_actor,
        status=InstallationSchedule.Status.SCHEDULED,
    )

    details = {
        'project_id': str(project.id),
        'scheduled_date': str(scheduled_date),
        'installation_manager_id': str(installation_manager.id),
    }
    if temporary_authorization is not None:
        details['temporary_duty_authorization_id'] = str(temporary_authorization.pk)
    event = audit(current_actor, 'installation_schedule.created', schedule.id, details)
    if temporary_authorization is not None:
        from .models import TemporaryDutyActivity
        TemporaryDutyActivity.objects.create(
            authorization=temporary_authorization,
            employee=current_actor,
            audit_event=event,
        )
    return schedule

@transaction.atomic
def complete_installation_schedule(
    actor,
    schedule_id,
):
    current_actor, temporary_authorization = _authorized_installation_actor(actor)

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

    details = {'project_id': str(schedule.project_id)}
    if temporary_authorization is not None:
        details['temporary_duty_authorization_id'] = str(temporary_authorization.pk)
    event = audit(current_actor, 'installation_schedule.completed', schedule.id, details)
    if temporary_authorization is not None:
        from .models import TemporaryDutyActivity
        TemporaryDutyActivity.objects.create(
            authorization=temporary_authorization,
            employee=current_actor,
            audit_event=event,
        )
    return schedule

@transaction.atomic
def cancel_installation_schedule(
    actor,
    schedule_id,
):
    current_actor, temporary_authorization = _authorized_installation_actor(actor)

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

    details = {'project_id': str(schedule.project_id)}
    if temporary_authorization is not None:
        details['temporary_duty_authorization_id'] = str(temporary_authorization.pk)
    event = audit(current_actor, 'installation_schedule.cancelled', schedule.id, details)
    if temporary_authorization is not None:
        from .models import TemporaryDutyActivity
        TemporaryDutyActivity.objects.create(
            authorization=temporary_authorization,
            employee=current_actor,
            audit_event=event,
        )

    return schedule
