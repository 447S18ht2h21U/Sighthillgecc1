from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Project, ProjectSalesStatusChange


AUTHORIZED_ROLES = frozenset({"CEO", "SALES_MANAGER"})


def validate_sales_status_change(actor, new_status, reason):
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) not in AUTHORIZED_ROLES
    ):
        raise PermissionDenied("Sales status change not authorized")

    if new_status not in Project.SalesStatus.values:
        raise ValidationError("Invalid sales opportunity status")

    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise ValidationError(
            "A reason of at least 10 characters is required"
        )

    return reason.strip()


@transaction.atomic
def change_project_sales_status(*, actor, project_id, new_status, reason):
    """Record a commercial status change without altering project health.

    Not exposed via an HTTP endpoint until authorization tests are accepted.
    """
    clean_reason = validate_sales_status_change(actor, new_status, reason)

    project = Project.objects.select_for_update().get(pk=project_id)
    previous_status = project.sales_status

    if previous_status == new_status:
        raise ValidationError("Sales opportunity already has this status")

    project.sales_status = new_status
    project.save(update_fields=["sales_status"])

    audit = ProjectSalesStatusChange.objects.create(
        project=project,
        changed_by=actor,
        previous_status=previous_status,
        new_status=new_status,
        reason=clean_reason,
    )
    return audit
