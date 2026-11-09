"""Trusted API actor verification for future MSR delegation endpoints.

Not registered in urls.py. Does not dispatch services, create records,
or activate delegated MSR visibility.

A future authenticated endpoint must call this with its actual DRF request.
Never use a client-supplied actor, role, approval flag, or user identifier.
"""

from types import MappingProxyType
from uuid import UUID

from rest_framework.exceptions import PermissionDenied

from .models import Role, User


ACTION_ROLES = MappingProxyType({
    "request": frozenset({Role.SALES_MANAGER}),
    "approve": frozenset({Role.CEO, Role.COMPTROLLER}),
    "surrender": frozenset({Role.SALES_ASSOCIATE}),
    "revoke": frozenset({Role.CEO, Role.COMPTROLLER}),
    "reassign": frozenset({Role.COMPTROLLER}),
})


def verified_delegation_actor(request, *, action):
    """Return a freshly loaded active User or deny.

    This is a role gate only. Services must independently validate project
    scope, actor participation, approval separation, and immutable evidence.
    """
    if type(action) is not str or action not in ACTION_ROLES:
        raise PermissionDenied("Unsupported delegation operation.")

    session_user = getattr(request, "user", None)
    if (
        session_user is None
        or getattr(session_user, "is_authenticated", False) is not True
    ):
        raise PermissionDenied("Authentication is required.")

    actor_id = getattr(session_user, "pk", None)
    if type(actor_id) is not UUID or actor_id.int == 0:
        raise PermissionDenied("Invalid authenticated identity.")

    verified = User.objects.filter(pk=actor_id, is_active=True).first()
    if verified is None:
        raise PermissionDenied("An active account is required.")

    if (
        verified.pk != actor_id
        or verified.is_active is not True
        or verified.role not in ACTION_ROLES[action]
    ):
        raise PermissionDenied("Delegation authority denied.")

    return verified


def actor_verification_grants_live_msr_access(*args, **kwargs):
    """A verified role alone never confers delegated project access."""
    return False