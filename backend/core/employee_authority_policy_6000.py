"""VERIDIAN initial deployment authority policy.

Approved by GECC on November 26, 2026.

This policy defines the six operational launch roles and
the approved distributor invoice authority matrix.

Deferred roles are retained for historical compatibility
and future expansion.

Defining launch roles here does not automatically enforce
account administration or application-wide session controls.
"""

from rest_framework.exceptions import PermissionDenied

from .models import Role


ACTIVE_DEPLOYMENT_ROLES = frozenset({
    Role.CEO,
    Role.COMPTROLLER,
    Role.SALES_MANAGER,
    Role.SALES_ASSOCIATE,
    Role.INSTALLATION_MANAGER,
    Role.TECHNICIAN,
})


DEFERRED_DEPLOYMENT_ROLES = frozenset({
    Role.MARKETING,
    Role.ACCOUNTS_PAYABLE_ASSOCIATE,
    Role.DATABASE_ADMINISTRATOR,
})


UPLOAD_DISTRIBUTOR_INVOICE = "UPLOAD_DISTRIBUTOR_INVOICE"

VERIFY_DISTRIBUTOR_INVOICE = "VERIFY_DISTRIBUTOR_INVOICE"

ALLOCATE_EXISTING_INVOICE = "ALLOCATE_EXISTING_INVOICE"


DISTRIBUTOR_INVOICE_AUTHORITY = {
    UPLOAD_DISTRIBUTOR_INVOICE: frozenset({
        Role.INSTALLATION_MANAGER,
        Role.COMPTROLLER,
    }),

    VERIFY_DISTRIBUTOR_INVOICE: frozenset({
        Role.INSTALLATION_MANAGER,
        Role.CEO,
    }),

    ALLOCATE_EXISTING_INVOICE: frozenset({
        Role.COMPTROLLER,
        Role.CEO,
    }),
}


def role_enabled_for_initial_deployment(role):
    return (
        isinstance(role, str)
        and role in ACTIVE_DEPLOYMENT_ROLES
    )


def distributor_invoice_action_allowed(role, action):
    if not role_enabled_for_initial_deployment(role):
        return False

    if not isinstance(action, str):
        return False

    return role in DISTRIBUTOR_INVOICE_AUTHORITY.get(
        action,
        frozenset(),
    )


def require_distributor_invoice_authority(actor, action):
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "is_active", False) is not True
        or not getattr(actor, "pk", None)
    ):
        raise PermissionDenied(
            "An active authenticated employee is required."
        )

    if not distributor_invoice_action_allowed(
        getattr(actor, "role", None),
        action,
    ):
        raise PermissionDenied(
            "You are not authorized to perform this "
            "distributor invoice action."
        )

    return actor
