"""Database-verified role eligibility, NOT operational authorization.

Callers must independently authenticate the request. A primary key alone
does not prove a person's identity. This helper never grants access.
"""

from .access_own_compensation_role_policy import (
    OWN_COMPENSATION_CODE,
    own_compensation_role_eligible,
)
from .models import User


def verified_own_compensation_role_eligible(actor):
    """Use the stored active role rather than an actor's stale role claim."""
    if actor is None or not isinstance(actor, User):
        return False

    if getattr(actor, "is_authenticated", False) is not True:
        return False

    actor_id = getattr(actor, "pk", None)
    if actor_id is None:
        return False

    stored = (
        User.objects.filter(pk=actor_id, is_active=True)
        .values("role")
        .first()
    )
    if stored is None:
        return False

    return own_compensation_role_eligible(
        role=stored["role"],
        permission_code=OWN_COMPENSATION_CODE,
        authenticated=True,
        active=True,
    )


def verified_identity_grants_live_access(*args, **kwargs):
    """Keep authorization disabled until approved integration."""
    return False