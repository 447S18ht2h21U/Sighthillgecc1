"""Project visibility for operational workflows, separate from commercial access."""

from django.utils import timezone

from .models import Project, ProjectTechnicalAssignment, Role, TemporaryProjectAccessAuthorization


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

    if user.role == Role.SALES_ASSOCIATE:
        return queryset.filter(sales_associate=user)

    if user.role == Role.TECHNICIAN:
        return queryset.filter(
            technical_assignments__technical_associate=user,
            technical_assignments__status=ProjectTechnicalAssignment.Status.ACTIVE,
            technical_assignments__effective_date__lte=timezone.localdate(),
        ).distinct()

    now = timezone.now()
    access_ids = TemporaryProjectAccessAuthorization.objects.filter(
        employee=user,
        status=TemporaryProjectAccessAuthorization.Status.APPROVED,
        starts_at__lte=now,
        ends_at__gt=now,
        revoked_at__isnull=True,
        closed_at__isnull=True,
        approved_by__is_active=True,
        temporary_duty__status="APPROVED",
        temporary_duty__starts_at__lte=now,
        temporary_duty__ends_at__gt=now,
        temporary_duty__revoked_at__isnull=True,
        temporary_duty__closed_at__isnull=True,
        temporary_duty__employee=user,
        temporary_duty__approved_by__is_active=True,
    ).values_list("project_id", flat=True)

    return queryset.filter(pk__in=access_ids)
