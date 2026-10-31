"""Database-free foundation for role-based MSR viewing.

This policy is enforced by the registered read-only MSR API.

Viewing never grants editing, approval, signing, financial reporting,
document generation, or temporary project delegation.
"""

from .models import Role


ALL_MSR_ROLES = frozenset({
    Role.CEO,
    Role.COMPTROLLER,
    Role.MARKETING,
    Role.SALES_MANAGER,
    Role.INSTALLATION_MANAGER,
})

ASSIGNED_MSR_ROLES = frozenset({
    Role.SALES_ASSOCIATE,
    Role.TECHNICIAN,
})

MSR_READ_ACTIONS = frozenset({"list", "retrieve"})


def msr_read_scope(actor, *, action, method):
    """Return the baseline scope for an authenticated, active role."""

    if actor is None:
        return None

    if not getattr(actor, "is_authenticated", False):
        return None

    if not getattr(actor, "is_active", False):
        return None

    if method != "GET" or action not in MSR_READ_ACTIONS:
        return None

    role = getattr(actor, "role", None)

    if role in ALL_MSR_ROLES:
        return "ALL_PROJECTS"

    if role in ASSIGNED_MSR_ROLES:
        return "ASSIGNED_PROJECTS"

    return None


def msr_project_read_permitted(actor, project, *, action, method,
                               active_technician_assignment=False):
    """Evaluate basic ownership without granting delegated access.

    Technician assignment evidence must come from a separately
    verified service. This function deliberately does not treat
    caller-supplied assignment evidence as sufficient authority.
    """

    scope = msr_read_scope(actor, action=action, method=method)

    if scope is None or project is None:
        return False

    if scope == "ALL_PROJECTS":
        return True

    if getattr(actor, "role", None) == Role.SALES_ASSOCIATE:
        actor_id = getattr(actor, "pk", None)
        project_owner_id = getattr(project, "sales_associate_id", None)
        return (
            actor_id is not None
            and project_owner_id is not None
            and actor_id == project_owner_id
        )

    if getattr(actor, "role", None) == Role.TECHNICIAN:
        return False

    return False


def msr_temporary_delegation_permitted(*args, **kwargs):
    """No live MSR delegation until independent controls exist."""
    return False


def msr_read_policy_grants_write(*args, **kwargs):
    """Viewing never provides record modification authority."""
    return False


def msr_read_policy_grants_signing(*args, **kwargs):
    """Viewing never provides signing authority."""
    return False


def msr_read_policy_grants_financial_access(*args, **kwargs):
    """Viewing never provides financial reporting authority."""
    return False