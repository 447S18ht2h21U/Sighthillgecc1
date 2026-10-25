from django.db import IntegrityError, connection, transaction
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

    from rest_framework.exceptions import PermissionDenied
    from .models import User

    if actor is None:
        raise PermissionDenied('An active authorized installation manager or comptroller is required.')

    current_actor = User.objects.filter(pk=actor.pk, is_active=True).first()
    if current_actor is None:
        raise PermissionDenied('An active authorized installation manager or comptroller is required.')

    temporary_authorization = None
    if current_actor.role not in (Role.INSTALLATION_MANAGER, Role.COMPTROLLER):
        from .models import TemporaryDutyAuthorization
        from .temporary_duty_services import is_temporary_duty_active

        candidates = TemporaryDutyAuthorization.objects.filter(
            employee=current_actor,
            permanent_role=current_actor.role,
            temporary_role=Role.INSTALLATION_MANAGER,
            status=TemporaryDutyAuthorization.Status.APPROVED,
        ).order_by('-starts_at', '-pk')

        temporary_authorization = next(
            (
                candidate for candidate in candidates
                if is_temporary_duty_active(candidate, current_actor)
            ),
            None,
        )
        if temporary_authorization is None:
            raise PermissionDenied('Valid temporary Installation Manager authority is required.')

    from .operational_visibility import operational_project_scope

    if not operational_project_scope(current_actor).filter(pk=project.pk).exists():
        raise PermissionDenied(
            'Project is outside the authorized operational scope.'
        )

    if technical_associate is None or not User.objects.filter(pk=technical_associate.pk, is_active=True, role=Role.TECHNICIAN).exists():
        raise ValidationError(
            'Assigned user must be an active technician.'
        )

    if ProjectTechnicalAssignment.objects.filter(
        project=project,
        technical_associate=technical_associate,
        status=ProjectTechnicalAssignment.Status.ACTIVE,
    ).exists():
        raise ValidationError(
            'This Technician already has an active assignment to this project. '
            'Review the active assignments below. '
            'You do not need to create another assignment.'
        )
    try:
        with transaction.atomic():
            assignment = ProjectTechnicalAssignment.objects.create(
                project=project,
                technical_associate=technical_associate,
                assigned_by=actor,
                effective_date=effective_date,
                status=ProjectTechnicalAssignment.Status.ACTIVE,
            )
    except IntegrityError as exc:
        cause = getattr(exc, '__cause__', None)
        constraint_name = getattr(
            getattr(cause, 'diag', None),
            'constraint_name',
            None,
        )

        sqlite_columns = {
            'core_projecttechnicalassignment.project_id',
            'core_projecttechnicalassignment.technical_associate_id',
        }
        sqlite_message = str(cause or exc)
        sqlite_prefix = 'UNIQUE constraint failed: '
        sqlite_duplicate = (
            sqlite_message.startswith(sqlite_prefix)
            and set(
                column.strip()
                for column in sqlite_message[len(sqlite_prefix):].split(',')
            ) == sqlite_columns
        )

        known_duplicate = (
            constraint_name == 'unique_active_technician_per_project'
            or (
                connection.vendor == 'sqlite'
                and sqlite_duplicate
            )
        )

        if not known_duplicate:
            raise

        raise ValidationError(
            'This Technician already has an active assignment to this project. '
            'Review the active assignments below. '
            'You do not need to create another assignment.'
        ) from exc

    from .services import audit

    payload = {
        "project_id": str(project.pk),
        "technical_associate_id": str(technical_associate.pk),
        "effective_date": effective_date.isoformat(),
    }
    if temporary_authorization is not None:
        payload["temporary_duty_authorization_id"] = str(
            temporary_authorization.pk
        )

    event = audit(
        current_actor,
        "TECHNICAL_ASSIGNMENT_CREATED",
        assignment.pk,
        payload,
    )

    if temporary_authorization is not None:
        from .models import TemporaryDutyActivity

        TemporaryDutyActivity.objects.create(
            authorization=temporary_authorization,
            employee=current_actor,
            audit_event=event,
        )

    return assignment

@transaction.atomic
def end_technical_assignment(
    actor,
    assignment_id,
):

    from rest_framework.exceptions import PermissionDenied
    from .models import User

    if actor is None:
        raise PermissionDenied('An active authorized installation manager or comptroller is required.')

    current_actor = User.objects.filter(pk=actor.pk, is_active=True).first()
    if current_actor is None:
        raise PermissionDenied('An active authorized installation manager or comptroller is required.')

    temporary_authorization = None
    if current_actor.role not in (Role.INSTALLATION_MANAGER, Role.COMPTROLLER):
        from .models import TemporaryDutyAuthorization
        from .temporary_duty_services import is_temporary_duty_active

        candidates = TemporaryDutyAuthorization.objects.filter(
            employee=current_actor,
            permanent_role=current_actor.role,
            temporary_role=Role.INSTALLATION_MANAGER,
            status=TemporaryDutyAuthorization.Status.APPROVED,
        ).order_by('-starts_at', '-pk')

        temporary_authorization = next(
            (
                candidate for candidate in candidates
                if is_temporary_duty_active(candidate, current_actor)
            ),
            None,
        )
        if temporary_authorization is None:
            raise PermissionDenied('Valid temporary Installation Manager authority is required.')

    assignment = (
        ProjectTechnicalAssignment.objects
        .select_for_update()
        .get(pk=assignment_id)
    )

    from .operational_visibility import operational_project_scope

    if not operational_project_scope(current_actor).filter(
        pk=assignment.project_id
    ).exists():
        raise PermissionDenied(
            'Project is outside the authorized operational scope.'
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

    from .services import audit

    payload = {
        "project_id": str(assignment.project_id),
        "technical_associate_id": str(assignment.technical_associate_id),
        "ended_at": assignment.ended_at.isoformat(),
    }
    if temporary_authorization is not None:
        payload["temporary_duty_authorization_id"] = str(
            temporary_authorization.pk
        )

    event = audit(
        current_actor,
        "TECHNICAL_ASSIGNMENT_ENDED",
        assignment.pk,
        payload,
    )

    if temporary_authorization is not None:
        from .models import TemporaryDutyActivity

        TemporaryDutyActivity.objects.create(
            authorization=temporary_authorization,
            employee=current_actor,
            audit_event=event,
        )

    return assignment