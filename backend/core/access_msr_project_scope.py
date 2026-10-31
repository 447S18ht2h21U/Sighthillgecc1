"""Read-only MSR project scope foundation.

This service supplies project scope to the registered read-only MSR API.

It does not authorize editing, approval, signing, document generation,
financial reporting, or temporary MSR delegation.
"""

from django.utils import timezone

from .access_msr_visibility_policy import msr_read_scope
from .models import Project, ProjectTechnicalAssignment, Role


def msr_visible_project_scope(actor, *, action="list", method="GET"):
    """Return only projects within the user's baseline MSR read scope."""

    projects = Project.objects.none()

    scope = msr_read_scope(actor, action=action, method=method)

    if scope is None:
        return projects

    if scope == "ALL_PROJECTS":
        return Project.objects.all()

    if scope != "ASSIGNED_PROJECTS":
        return projects

    role = getattr(actor, "role", None)

    if role == Role.SALES_ASSOCIATE:
        actor_id = getattr(actor, "pk", None)

        if actor_id is None:
            return projects

        return Project.objects.filter(
            sales_associate_id=actor_id,
        )

    if role == Role.TECHNICIAN:
        actor_id = getattr(actor, "pk", None)

        if actor_id is None:
            return projects

        return Project.objects.filter(
            technical_assignments__technical_associate_id=actor_id,
            technical_assignments__status=(
                ProjectTechnicalAssignment.Status.ACTIVE
            ),
            technical_assignments__ended_at__isnull=True,
            technical_assignments__effective_date__lte=(
                timezone.localdate()
            ),
        ).distinct()

    return projects