"""Controlled approval of versioned employee compensation plans."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .access_employee_payroll_plan_policy import (
    validate_compensation_approval_separation,
)
from .models import (
    Employee,
    EmployeeCompensationPlan,
    EmployeePayrollRecord,
    Role,
    User,
)
from .services import audit


@transaction.atomic
def approve_employee_compensation_plan(actor, plan_id, reason):
    """Approve eligible draft terms with independent authority and audit.

    Retroactive effective dates overlapping already approved or paid
    payroll are blocked; corrections require a separate approved process.
    """
    actor_id = getattr(actor, "pk", None)

    current_actor = (
        User.objects.filter(pk=actor_id, is_active=True).first()
        if actor_id is not None else None
    )

    if current_actor is None or current_actor.role != Role.COMPTROLLER:
        raise PermissionDenied(
            "An active Comptroller account is required."
        )

    if not isinstance(reason, str):
        raise ValidationError("A written approval reason is required.")

    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError(
            "An approval reason of 1 to 1000 characters is required."
        )

    plan = (
        EmployeeCompensationPlan.objects
        .select_for_update()
        .select_related("employee", "employee__user")
        .get(pk=plan_id)
    )

    if plan.status != EmployeeCompensationPlan.Status.DRAFT:
        raise ValidationError("Only draft compensation plans may be approved.")

    if plan.employee.status != Employee.Status.ACTIVE:
        raise ValidationError(
            "The employee must be active to approve compensation."
        )

    try:
        validate_compensation_approval_separation(
            approver_user_id=current_actor.pk,
            employee_user_id=plan.employee.user_id,
            requester_user_id=plan.created_by_id,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if not isinstance(plan.compensation_terms, dict) or not plan.compensation_terms:
        raise ValidationError("Compensation terms are required.")

    if type(plan.version) is not int or plan.version <= 0:
        raise ValidationError("A positive compensation version is required.")

    if plan.effective_date is None:
        raise ValidationError("A valid effective date is required.")

    conflicting = (
        EmployeeCompensationPlan.objects
        .filter(
            employee_id=plan.employee_id,
            status=EmployeeCompensationPlan.Status.APPROVED,
            effective_date=plan.effective_date,
        )
        .exclude(pk=plan.pk)
        .exists()
    )
    if conflicting:
        raise ValidationError(
            "Another approved compensation plan already uses this date."
        )

    # Do not approve a new date that falls within any previously
    # approved or settled earning period, even if that period was
    # calculated under an earlier compensation version.
    processed_overlap = EmployeePayrollRecord.objects.filter(
        employee_id=plan.employee_id,
        status__in=(
            EmployeePayrollRecord.Status.APPROVED,
            EmployeePayrollRecord.Status.PAID,
        ),
        payroll_period_end__gte=plan.effective_date,
    ).exists()

    if processed_overlap:
        raise ValidationError(
            "The effective date overlaps previously approved or paid "
            "payroll. Use the separately reviewed correction process."
        )

    plan.status = EmployeeCompensationPlan.Status.APPROVED
    plan.approved_by = current_actor
    plan.approved_at = timezone.now()

    plan.save(
        update_fields=["status", "approved_by", "approved_at"]
    )

    audit(
        current_actor,
        "employee.compensation.approved",
        plan.pk,
        {
            "employee_id": str(plan.employee_id),
            "version": plan.version,
            "effective_date": plan.effective_date.isoformat(),
            "reason": reason,
        },
    )

    return plan
