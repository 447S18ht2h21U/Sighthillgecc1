"""Project visibility for operational workflows, separate from commercial access."""

from django.utils import timezone

from .models import Project, ProjectTechnicalAssignment, Role, TemporaryDutyAuthorization
from .temporary_duty_services import is_temporary_duty_active


def operational_project_scope(user):
    """Return projects visible to an active user in operational workflows."""
    queryset = Project.objects.all()

    if user is None or not user.is_authenticated or not user.is_active:
        return queryset.none()

    if user.role in (
        Role.COMPTROLLER,
        Role.SALES_MANAGER,
        Role.INSTALLATION_MANAGER,
    ):
        return queryset

    authorizations = TemporaryDutyAuthorization.objects.filter(
        employee=user,
        permanent_role=user.role,
        temporary_role=Role.INSTALLATION_MANAGER,
        status=TemporaryDutyAuthorization.Status.APPROVED,
    )

    if any(is_temporary_duty_active(item, user) for item in authorizations):
        return queryset

    if user.role == Role.SALES_ASSOCIATE:
        return queryset.filter(sales_associate=user)

    if user.role == Role.TECHNICIAN:
        return queryset.filter(
            technical_assignments__technical_associate=user,
            technical_assignments__status=ProjectTechnicalAssignment.Status.ACTIVE,
            technical_assignments__effective_date__lte=timezone.localdate(),
        ).distinct()

    return queryset.none()
