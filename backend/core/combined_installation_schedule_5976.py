"""Atomic installation scheduling and technician assignment."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import (
    Project,
    InstallationSchedule,
    ProjectTechnicalAssignment,
    Role,
    User,
)
from .operational_visibility import operational_project_scope
from .installation_schedule_services import create_future_installation_schedule
from .technical_assignment_services import create_technical_assignment


class CombinedScheduleInput(serializers.Serializer):
    project = serializers.UUIDField()
    scheduled_date = serializers.DateField()
    technicians = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=25,
    )

    def validate_technicians(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "Select each technician only once."
            )
        return values


@transaction.atomic
def schedule_and_assign(*, actor, project_id, scheduled_date, technician_ids):
    """Save the appointment and every new assignment, or save nothing."""

    current_actor = User.objects.filter(
        pk=actor.pk,
        is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()

    if current_actor is None:
        raise PermissionDenied(
            "An active Installation Manager is required."
        )

    if not operational_project_scope(current_actor).filter(
        pk=project_id
    ).exists():
        raise PermissionDenied(
            "Project is outside your authorized operational scope."
        )

    project = get_object_or_404(
        Project.objects.select_for_update(),
        pk=project_id,
    )

    if project.state == "CANCELLED":
        raise ValidationError("A cancelled project cannot be scheduled.")

    technician_ids = list(technician_ids)

    if not technician_ids or len(technician_ids) > 25:
        raise ValidationError(
            "Select at least one technician, with a maximum of 25."
        )

    if len(technician_ids) != len(set(technician_ids)):
        raise ValidationError("Select each technician only once.")

    if InstallationSchedule.objects.filter(
        project=project,
        status__in=[
            InstallationSchedule.Status.SCHEDULED,
            InstallationSchedule.Status.COMPLETED,
        ],
    ).exists():
        raise ValidationError(
            "This project already has a scheduled or completed "
            "installation. Review the existing record."
        )

    technicians = {
        user.pk: user
        for user in User.objects.select_for_update().filter(
            pk__in=technician_ids,
            is_active=True,
            role=Role.TECHNICIAN,
        ).order_by("pk")
    }

    if len(technicians) != len(technician_ids):
        raise ValidationError(
            "One or more selected technicians are no longer available "
            "for assignment."
        )

    existing = list(
        ProjectTechnicalAssignment.objects.filter(
            project=project,
            status=ProjectTechnicalAssignment.Status.ACTIVE,
        ).select_for_update()
    )

    if existing:
        raise ValidationError(
            "This project already has active technician assignments. "
            "Review those assignments before creating a combined schedule."
        )

    # The existing service retains all commercial signature,
    # cancellation, payment, proposed-date and role safeguards.
    schedule = create_future_installation_schedule(
        actor=current_actor,
        project=project,
        scheduled_date=scheduled_date,
        installation_manager=current_actor,
    )

    assignments = []

    for technician_id in technician_ids:
        assignment = create_technical_assignment(
            actor=current_actor,
            project=project,
            technical_associate=technicians[technician_id],
            effective_date=scheduled_date,
        )
        assignments.append(assignment)

    return {
        "project_id": str(project.pk),
        "schedule_id": str(schedule.pk),
        "scheduled_date": scheduled_date.isoformat(),
        "installation_manager_id": str(current_actor.pk),
        "assignments": [
            {
                "id": str(assignment.pk),
                "technician_id": str(assignment.technical_associate_id),
            }
            for assignment in assignments
        ],
        "installation_authorized": False,
        "installation_started": False,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create(request):
    data = CombinedScheduleInput(data=request.data)
    data.is_valid(raise_exception=True)

    values = data.validated_data

    result = schedule_and_assign(
        actor=request.user,
        project_id=values["project"],
        scheduled_date=values["scheduled_date"],
        technician_ids=values["technicians"],
    )

    return Response(result, status=201)
