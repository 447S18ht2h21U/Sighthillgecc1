"""Database-confirmed role authorization for financial reporting.

This module does not grant compensation disclosure permissions.
It does not authorize payroll payments or modify report records.

Report services must explicitly invoke this helper before sensitive
financial operations. The current database account and role are
authoritative, not potentially stale caller-provided user objects.
"""

from rest_framework.exceptions import PermissionDenied

from .models import Role, User


ALLOWED_REPORTING_ROLES = frozenset({
    Role.SALES_MANAGER,
    Role.COMPTROLLER,
})


def require_financial_reporting_role(actor, required_role):
    """Require an active database account holding the specified report role."""

    if required_role not in ALLOWED_REPORTING_ROLES:
        raise PermissionDenied(
            "The requested financial reporting role is not authorized."
        )

    actor_id = getattr(actor, "pk", None)

    if actor_id is None:
        raise PermissionDenied(
            "An active authorized financial reporting account is required."
        )

    current_actor = (
        User.objects
        .filter(pk=actor_id, is_active=True)
        .first()
    )

    if current_actor is None or current_actor.role != required_role:
        raise PermissionDenied(
            "An active user with the required financial reporting role is required."
        )

    return current_actor