"""Temporary-duty eligibility and independent approval rules."""

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role


ALLOWED_TEMPORARY_ROLES = {
    Role.CEO: frozenset({Role.SALES_MANAGER, Role.INSTALLATION_MANAGER}),
    Role.COMPTROLLER: frozenset({Role.SALES_MANAGER, Role.INSTALLATION_MANAGER}),
    Role.SALES_MANAGER: frozenset({Role.SALES_ASSOCIATE, Role.TECHNICIAN}),
    Role.INSTALLATION_MANAGER: frozenset({Role.SALES_ASSOCIATE, Role.TECHNICIAN}),
}

AUTHORIZED_APPROVERS = {
    Role.CEO: frozenset({Role.COMPTROLLER}),
    Role.COMPTROLLER: frozenset({Role.CEO}),
    Role.SALES_MANAGER: frozenset({Role.CEO, Role.COMPTROLLER}),
    Role.INSTALLATION_MANAGER: frozenset({Role.CEO, Role.COMPTROLLER}),
}


def request_temporary_duty(*, employee, temporary_role, requested_by, reason, starts_at, ends_at):
    """Create an unauthorised request with a durable audit record."""
    from django.db import transaction
    from .models import TemporaryDutyAuthorization
    from .services import audit

    if employee is None or requested_by is None:
        raise ValidationError("Employee and requester are required.")

    if requested_by.pk != employee.pk and requested_by.role not in (Role.CEO, Role.COMPTROLLER):
        raise PermissionDenied("Only the employee, CEO, or Comptroller may submit this request.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A justification is required.")

    if temporary_role not in ALLOWED_TEMPORARY_ROLES.get(employee.role, frozenset()):
        raise ValidationError("This temporary role is not permitted for the employee.")

    validate_temporary_duty_period(starts_at, ends_at)

    with transaction.atomic():
        authorization = TemporaryDutyAuthorization.objects.create(
            employee=employee,
            permanent_role=employee.role,
            temporary_role=temporary_role,
            requested_by=requested_by,
            reason=reason.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            status=TemporaryDutyAuthorization.Status.REQUESTED,
        )
        audit(
            requested_by,
            "TEMPORARY_DUTY_REQUESTED",
            authorization.id,
            {
                "employee_id": str(employee.pk),
                "permanent_role": employee.role,
                "temporary_role": temporary_role,
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "reason": reason.strip(),
            },
        )
        return authorization

def approve_temporary_duty(*, authorization_id, approver):
    """Independently approve a pending temporary-duty request."""
    from django.db import transaction
    from django.utils import timezone
    from .models import TemporaryDutyAuthorization
    from .services import audit

    if approver is None or not approver.is_active:
        raise PermissionDenied("An active approver is required.")

    with transaction.atomic():
        authorization = (
            TemporaryDutyAuthorization.objects
            .select_for_update()
            .select_related("employee")
            .get(pk=authorization_id)
        )

        if authorization.status != TemporaryDutyAuthorization.Status.REQUESTED:
            raise ValidationError("Only requested temporary duties may be approved.")

        employee = authorization.employee

        if not employee.is_active:
            raise PermissionDenied("The employee account must be active.")

        if authorization.permanent_role != employee.role:
            raise ValidationError("The employee's permanent role has changed.")

        validate_temporary_duty_eligibility(
            employee, authorization.temporary_role, approver
        )
        validate_temporary_duty_period(
            authorization.starts_at, authorization.ends_at
        )

        decided_at = timezone.now()
        authorization.status = TemporaryDutyAuthorization.Status.APPROVED
        authorization.approved_by = approver
        authorization.decided_at = decided_at
        authorization.save(update_fields=["status", "approved_by", "decided_at"])

        audit(
            approver,
            "TEMPORARY_DUTY_APPROVED",
            authorization.id,
            {
                "employee_id": str(employee.pk),
                "permanent_role": authorization.permanent_role,
                "temporary_role": authorization.temporary_role,
                "starts_at": authorization.starts_at.isoformat(),
                "ends_at": authorization.ends_at.isoformat(),
                "decided_at": decided_at.isoformat(),
            },
        )
        return authorization

def reject_temporary_duty(*, authorization_id, decision_maker, reason):
    """Independently reject a pending temporary-duty request."""
    from django.db import transaction
    from django.utils import timezone
    from .models import TemporaryDutyAuthorization
    from .services import audit

    if decision_maker is None or not decision_maker.is_active:
        raise PermissionDenied("An active decision-maker is required.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A rejection reason is required.")

    with transaction.atomic():
        authorization = (
            TemporaryDutyAuthorization.objects
            .select_for_update()
            .select_related("employee")
            .get(pk=authorization_id)
        )

        if authorization.status != TemporaryDutyAuthorization.Status.REQUESTED:
            raise ValidationError("Only requested temporary duties may be rejected.")

        employee = authorization.employee

        validate_temporary_duty_eligibility(
            employee, authorization.temporary_role, decision_maker
        )

        decided_at = timezone.now()
        authorization.status = TemporaryDutyAuthorization.Status.REJECTED
        authorization.decided_at = decided_at
        authorization.save(update_fields=["status", "decided_at"])

        audit(
            decision_maker,
            "TEMPORARY_DUTY_REJECTED",
            authorization.id,
            {
                "employee_id": str(employee.pk),
                "temporary_role": authorization.temporary_role,
                "reason": reason.strip(),
                "decided_at": decided_at.isoformat(),
            },
        )
        return authorization

def revoke_temporary_duty(*, authorization_id, revoked_by, reason):
    """Revoke previously approved temporary authority with an audit record."""
    from django.db import transaction
    from django.utils import timezone
    from .models import TemporaryDutyAuthorization
    from .services import audit

    if revoked_by is None or not revoked_by.is_active:
        raise PermissionDenied("An active revoking officer is required.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A revocation reason is required.")

    with transaction.atomic():
        authorization = (
            TemporaryDutyAuthorization.objects
            .select_for_update()
            .select_related("employee")
            .get(pk=authorization_id)
        )

        if authorization.status != TemporaryDutyAuthorization.Status.APPROVED:
            raise ValidationError("Only approved temporary duties may be revoked.")

        employee = authorization.employee

        if revoked_by.pk == employee.pk:
            raise PermissionDenied("Employees cannot revoke their own temporary duties.")

        if revoked_by.role not in (Role.CEO, Role.COMPTROLLER):
            raise PermissionDenied("Only the CEO or Comptroller may revoke temporary duties.")

        revoked_at = timezone.now()
        authorization.status = TemporaryDutyAuthorization.Status.REVOKED
        authorization.revoked_at = revoked_at
        authorization.save(update_fields=["status", "revoked_at"])

        audit(
            revoked_by,
            "TEMPORARY_DUTY_REVOKED",
            authorization.id,
            {
                "employee_id": str(employee.pk),
                "temporary_role": authorization.temporary_role,
                "reason": reason.strip(),
                "revoked_at": revoked_at.isoformat(),
            },
        )
        return authorization

def complete_temporary_duty(*, authorization_id, closed_by, reason):
    """Close approved temporary authority with an auditable decision."""
    from django.db import transaction
    from django.utils import timezone
    from .models import TemporaryDutyAuthorization
    from .services import audit

    if closed_by is None or not closed_by.is_active:
        raise PermissionDenied("An active closing officer is required.")

    if closed_by.role not in (Role.CEO, Role.COMPTROLLER):
        raise PermissionDenied("Only the CEO or Comptroller may close temporary duties.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A completion reason is required.")

    with transaction.atomic():
        authorization = (
            TemporaryDutyAuthorization.objects
            .select_for_update()
            .select_related("employee")
            .get(pk=authorization_id)
        )

        if authorization.status != TemporaryDutyAuthorization.Status.APPROVED:
            raise ValidationError("Only approved temporary duties may be completed.")

        if closed_by.pk == authorization.employee_id:
            raise PermissionDenied("Employees cannot close their own temporary duties.")

        closed_at = timezone.now()
        authorization.status = TemporaryDutyAuthorization.Status.COMPLETED
        authorization.closed_at = closed_at
        authorization.save(update_fields=["status", "closed_at"])

        audit(
            closed_by,
            "TEMPORARY_DUTY_COMPLETED",
            authorization.id,
            {
                "employee_id": str(authorization.employee_id),
                "temporary_role": authorization.temporary_role,
                "reason": reason.strip(),
                "closed_at": closed_at.isoformat(),
            },
        )
        return authorization

def close_expired_temporary_duties(*, processed_by):
    """Close expired approved authorizations with individual audit records."""
    from django.db import transaction
    from django.utils import timezone
    from .models import TemporaryDutyAuthorization
    from .services import audit

    if processed_by is None or not processed_by.is_active:
        raise PermissionDenied("An active processing officer is required.")

    if processed_by.role not in (Role.CEO, Role.COMPTROLLER):
        raise PermissionDenied("Only the CEO or Comptroller may process expired duties.")

    closed_count = 0

    with transaction.atomic():
        now = timezone.now()
        expired = (
            TemporaryDutyAuthorization.objects
            .select_for_update()
            .filter(
                status=TemporaryDutyAuthorization.Status.APPROVED,
                ends_at__lte=now,
            )
            .order_by("ends_at", "pk")
        )

        for authorization in expired:
            authorization.status = TemporaryDutyAuthorization.Status.COMPLETED
            authorization.closed_at = now
            authorization.save(update_fields=["status", "closed_at"])

            audit(
                processed_by,
                "TEMPORARY_DUTY_EXPIRED",
                authorization.id,
                {
                    "employee_id": str(authorization.employee_id),
                    "temporary_role": authorization.temporary_role,
                    "ends_at": authorization.ends_at.isoformat(),
                    "closed_at": now.isoformat(),
                },
            )
            closed_count += 1

    return closed_count

def validate_temporary_duty_period(starts_at, ends_at, *, now=None):
    """Validate the requested effective period without activating authority."""
    from django.utils import timezone

    if starts_at is None or ends_at is None:
        raise ValidationError("Temporary-duty start and end dates are required.")

    if timezone.is_naive(starts_at) or timezone.is_naive(ends_at):
        raise ValidationError("Temporary-duty dates must include timezone information.")

    if ends_at <= starts_at:
        raise ValidationError("Temporary-duty end date must be later than its start date.")

    current_time = timezone.now() if now is None else now
    if timezone.is_naive(current_time):
        raise ValidationError("The comparison time must include timezone information.")

    if ends_at <= current_time:
        raise ValidationError("Temporary-duty authorization cannot be approved after its end date.")

    return True

def is_temporary_duty_active(authorization, employee, *, now=None):
    """Check whether independently approved temporary authority is effective."""
    from django.utils import timezone
    from .models import TemporaryDutyAuthorization

    if authorization is None or employee is None:
        return False

    authorization = TemporaryDutyAuthorization.objects.filter(pk=authorization.pk).first()
    if authorization is None or authorization.status != TemporaryDutyAuthorization.Status.APPROVED:
        return False

    if not employee.is_active:
        return False
    if authorization.employee_id != employee.pk:
        return False

    if authorization.permanent_role != employee.role:
        return False

    if authorization.temporary_role not in ALLOWED_TEMPORARY_ROLES.get(employee.role, frozenset()):
        return False

    if authorization.approved_by_id is None or authorization.approved_by_id == employee.pk:
        return False

    if authorization.decided_at is None:
        return False

    from .models import User

    if not User.objects.filter(pk=employee.pk, is_active=True, role=authorization.permanent_role).exists():
        return False

    if not User.objects.filter(pk=authorization.approved_by_id, is_active=True, role__in=AUTHORIZED_APPROVERS.get(authorization.permanent_role, frozenset())).exists():
        return False

    current_time = timezone.now() if now is None else now
    if timezone.is_naive(current_time):
        return False

    if not (authorization.starts_at <= current_time < authorization.ends_at):
        return False

    if authorization.decided_at > current_time:
        return False

    if authorization.revoked_at is not None or authorization.closed_at is not None:
        return False

    return True

def validate_temporary_duty_eligibility(employee, temporary_role, approver):
    """Validate role eligibility and independent approval authority."""
    if not employee or not approver:
        raise ValidationError("Employee and approver are required.")

    if employee.pk == approver.pk:
        raise PermissionDenied("Employees cannot approve their own temporary duties.")

    if temporary_role not in ALLOWED_TEMPORARY_ROLES.get(employee.role, frozenset()):
        raise ValidationError("This temporary role is not permitted for the employee.")

    if approver.role not in AUTHORIZED_APPROVERS.get(employee.role, frozenset()):
        raise PermissionDenied("This approver is not authorized for the employee's temporary duties.")

    return True