"""Independently controlled, project-specific temporary access services."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Role,
    TemporaryDutyAuthorization,
    TemporaryProjectAccessAuthorization,
)
from .services import audit
from .temporary_duty_services import (
    AUTHORIZED_APPROVERS,
    is_temporary_duty_active,
)


def validate_project_access_request(*, employee, temporary_duty, starts_at, ends_at):
    if employee is None or not employee.is_active:
        raise PermissionDenied("An active employee is required.")

    if temporary_duty is None:
        raise ValidationError("A temporary-duty authorization is required.")

    if not is_temporary_duty_active(temporary_duty, employee):
        raise PermissionDenied("An active, approved temporary duty is required.")

    if starts_at is None or ends_at is None:
        raise ValidationError("Start and end dates are required.")

    if timezone.is_naive(starts_at) or timezone.is_naive(ends_at):
        raise ValidationError("Dates must include timezone information.")

    if ends_at <= starts_at:
        raise ValidationError("End date must follow start date.")

    if ends_at <= timezone.now():
        raise ValidationError("Access cannot end in the past.")

    if starts_at < temporary_duty.starts_at or ends_at > temporary_duty.ends_at:
        raise ValidationError("Access must remain within the temporary-duty period.")

    return True


def request_temporary_project_access(
    *, employee, temporary_duty, project, requested_by,
    reason, starts_at, ends_at
):
    """Create an audited, pending project-specific access request."""
    if employee is None or requested_by is None or project is None:
        raise ValidationError("Employee, requester, and project are required.")

    if not requested_by.is_active:
        raise PermissionDenied("The requester must be active.")

    if (
        requested_by.pk != employee.pk
        and requested_by.role not in (Role.CEO, Role.COMPTROLLER)
    ):
        raise PermissionDenied("The requester is not authorized.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A justification is required.")

    validate_project_access_request(
        employee=employee,
        temporary_duty=temporary_duty,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    with transaction.atomic():
        authorization = TemporaryProjectAccessAuthorization.objects.create(
            temporary_duty=temporary_duty,
            employee=employee,
            project=project,
            requested_by=requested_by,
            reason=reason.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            status=TemporaryProjectAccessAuthorization.Status.REQUESTED,
        )

        audit(
            requested_by,
            "TEMPORARY_PROJECT_ACCESS_REQUESTED",
            authorization.id,
            {
                "employee_id": str(employee.pk),
                "temporary_duty_id": str(temporary_duty.pk),
                "project_id": str(project.pk),
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "reason": reason.strip(),
            },
        )

        return authorization


def approve_temporary_project_access(*, authorization_id, approver):
    """Independently approve a project-specific temporary-access request."""
    if approver is None or not approver.is_active:
        raise PermissionDenied("An active approver is required.")

    with transaction.atomic():
        authorization = (
            TemporaryProjectAccessAuthorization.objects
            .select_for_update()
            .select_related("employee", "temporary_duty", "requested_by")
            .get(pk=authorization_id)
        )

        if authorization.status != TemporaryProjectAccessAuthorization.Status.REQUESTED:
            raise ValidationError("Only pending project-access requests may be approved.")

        employee = authorization.employee

        if approver.pk == employee.pk or approver.pk == authorization.requested_by_id:
            raise PermissionDenied("Independent approval is required.")

        allowed_roles = AUTHORIZED_APPROVERS.get(employee.role, frozenset())
        if approver.role not in allowed_roles:
            raise PermissionDenied("This approver is not authorized.")

        validate_project_access_request(
            employee=employee,
            temporary_duty=authorization.temporary_duty,
            starts_at=authorization.starts_at,
            ends_at=authorization.ends_at,
        )

        decided_at = timezone.now()
        authorization.status = TemporaryProjectAccessAuthorization.Status.APPROVED
        authorization.approved_by = approver
        authorization.decided_at = decided_at
        authorization.save(update_fields=["status", "approved_by", "decided_at"])

        audit(
            approver,
            "TEMPORARY_PROJECT_ACCESS_APPROVED",
            authorization.id,
            {
                "employee_id": str(employee.pk),
                "temporary_duty_id": str(authorization.temporary_duty_id),
                "project_id": str(authorization.project_id),
                "starts_at": authorization.starts_at.isoformat(),
                "ends_at": authorization.ends_at.isoformat(),
                "decided_at": decided_at.isoformat(),
            },
        )
        return authorization


def revoke_temporary_project_access(*, authorization_id, revoked_by, reason):
    """Revoke approved project-specific temporary access with an audit record."""
    if revoked_by is None or not revoked_by.is_active:
        raise PermissionDenied("An active revoking administrator is required.")

    if revoked_by.role not in (Role.CEO, Role.COMPTROLLER):
        raise PermissionDenied("Only the CEO or Comptroller may revoke temporary project access.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A revocation reason is required.")

    with transaction.atomic():
        authorization = (
            TemporaryProjectAccessAuthorization.objects
            .select_for_update()
            .get(pk=authorization_id)
        )

        if authorization.status != TemporaryProjectAccessAuthorization.Status.APPROVED:
            raise ValidationError("Only approved project access may be revoked.")

        revoked_at = timezone.now()
        authorization.status = TemporaryProjectAccessAuthorization.Status.REVOKED
        authorization.revoked_at = revoked_at
        authorization.save(update_fields=["status", "revoked_at"])

        audit(
            revoked_by,
            "TEMPORARY_PROJECT_ACCESS_REVOKED",
            authorization.id,
            {
                "employee_id": str(authorization.employee_id),
                "temporary_duty_id": str(authorization.temporary_duty_id),
                "project_id": str(authorization.project_id),
                "revoked_at": revoked_at.isoformat(),
                "reason": reason.strip(),
            },
        )
        return authorization
