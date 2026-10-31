"""Non-operational policy for viewing one's own compensation.

This function evaluates role eligibility only. It does not authenticate an
account against the database, grant effective permissions, register routes,
or authorize reading records. Live access remains default-deny.
"""

from .models import Role

OWN_COMPENSATION_CODE = "compensation.own.view"

ELIGIBLE_ROLES = frozenset(value for value, label in Role.choices)


def own_compensation_role_eligible(
    *,
    role,
    permission_code,
    authenticated,
    active,
):
    """Evaluate eligibility, not effective authorization."""
    return (
        authenticated is True
        and active is True
        and isinstance(role, str)
        and role in ELIGIBLE_ROLES
        and permission_code == OWN_COMPENSATION_CODE
    )


def own_compensation_policy_grants_live_access(*args, **kwargs):
    """No grants until a separately tested authorization integration."""
    return False