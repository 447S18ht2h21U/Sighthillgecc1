"""Read-only ownership scopes for VERIDIAN compensation.

Self-service visibility requires an active authenticated User
linked by an explicit Employee.user or Contractor.user relationship.

These helpers do not authorize payment approval, issuance, or changes.
They are not yet connected to live API endpoints.
"""

from .models import (
    ContractorPaymentRecord,
    EmployeePayrollRecord,
    User,
)


def _active_account_id(actor):
    """Resolve active account identity from the database, not stale role data."""
    if actor is None:
        return None

    if not getattr(actor, "is_authenticated", False):
        return None

    user_id = getattr(actor, "pk", None)

    if user_id is None:
        return None

    return (
        User.objects
        .filter(pk=user_id, is_active=True)
        .values_list("pk", flat=True)
        .first()
    )


def own_employee_payroll_scope(actor):
    """Employee payroll for the authenticated user's linked identity only."""
    user_id = _active_account_id(actor)

    if user_id is None:
        return EmployeePayrollRecord.objects.none()

    return EmployeePayrollRecord.objects.filter(
        employee__user_id=user_id,
    )


def own_contractor_payment_scope(actor):
    """Contractor payments for the user's linked contractor identity only."""
    user_id = _active_account_id(actor)

    if user_id is None:
        return ContractorPaymentRecord.objects.none()

    return ContractorPaymentRecord.objects.filter(
        engagement__contractor__user_id=user_id,
    )
