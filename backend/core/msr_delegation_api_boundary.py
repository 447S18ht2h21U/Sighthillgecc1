"""Unregistered, non-operational delegation command preparation.

Validates request method, authoritative actor, and client payload.
Never executes service operations or grants MSR access.
"""

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from rest_framework.exceptions import PermissionDenied

from .msr_delegation_api_actor import verified_delegation_actor
from .msr_delegation_api_contract import (
    parse_request_payload,
    parse_approval_payload,
    parse_termination_payload,
    parse_reassignment_payload,
)


PARSERS = MappingProxyType({
    "request": parse_request_payload,
    "approve": parse_approval_payload,
    "surrender": parse_termination_payload,
    "revoke": parse_termination_payload,
    "reassign": parse_reassignment_payload,
})

TERMINATION_KINDS = MappingProxyType({
    "surrender": "VOLUNTARY_SURRENDER",
    "revoke": "ADMINISTRATIVE_REVOCATION",
})


@dataclass(frozen=True)
class PreparedDelegationCommand:
    action: str
    actor_id: UUID
    arguments: tuple


def prepare_delegation_command(request, *, action):
    """Prepare evidence only. Execution is a separate, prohibited step."""
    if type(action) is not str or action not in PARSERS:
        raise PermissionDenied("Unsupported delegation operation.")

    if getattr(request, "method", None) != "POST":
        raise PermissionDenied("POST is required.")

    actor = verified_delegation_actor(request, action=action)
    payload = getattr(request, "data", None)
    arguments = PARSERS[action](payload)

    if action in TERMINATION_KINDS:
        if arguments["kind"] != TERMINATION_KINDS[action]:
            raise PermissionDenied("Termination action and kind do not match.")

    # A tuple of key/value pairs avoids a mutable command dictionary.
    # Nested mutable values are not permitted by the existing parsers.
    return PreparedDelegationCommand(
        action=action,
        actor_id=actor.pk,
        arguments=tuple(sorted(arguments.items())),
    )


def execute_prepared_delegation_command(*args, **kwargs):
    """Operational dispatch stays disabled pending separate review."""
    raise PermissionDenied("Operational MSR delegation is not enabled.")


def boundary_grants_live_msr_access(*args, **kwargs):
    return False