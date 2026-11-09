"""Non-executable mapping of prepared delegation commands to service contracts.

No database queries, service calls, route registration, or access activation.
Route target identifiers must be supplied by trusted URL routing, not JSON.
"""

from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from rest_framework.exceptions import PermissionDenied

from .msr_delegation_api_boundary import PreparedDelegationCommand


CONTRACTS = MappingProxyType({
    "request": (
        "create_fixed_msr_delegation_request", "manager_id", None,
        frozenset({
            "recipient_id", "source_associate_id", "project_ids",
            "starts_at", "ends_at", "reason",
        }),
    ),
    "approve": (
        "approve_fixed_msr_delegation", "approver_id", "request_id",
        frozenset({"reason"}),
    ),
    "surrender": (
        "terminate_fixed_msr_delegation", "actor_id", "decision_id",
        frozenset({"kind", "reason"}),
    ),
    "revoke": (
        "terminate_fixed_msr_delegation", "actor_id", "decision_id",
        frozenset({"kind", "reason"}),
    ),
    "reassign": (
        "reassign_project_with_msr_invalidation", "actor_id", "project_id",
        frozenset({"new_owner_id", "reason"}),
    ),
})


@dataclass(frozen=True)
class DelegationServicePlan:
    operation: str
    arguments: tuple


def prepare_service_plan(command, *, route_target=None):
    """Verify immutable command shape and bind trusted route/actor identities."""
    if type(command) is not PreparedDelegationCommand:
        raise PermissionDenied("Invalid prepared command.")

    if type(command.actor_id) is not UUID or not command.actor_id.int:
        raise PermissionDenied("Invalid trusted actor identity.")

    if type(command.action) is not str or command.action not in CONTRACTS:
        raise PermissionDenied("Unknown delegation operation.")

    operation, actor_field, target_field, expected = CONTRACTS[command.action]

    if type(command.arguments) is not tuple:
        raise PermissionDenied("Invalid command arguments.")

    try:
        values = dict(command.arguments)
    except (TypeError, ValueError):
        raise PermissionDenied("Invalid command argument structure.") from None

    if (
        len(values) != len(command.arguments)
        or set(values) != expected
        or any(type(key) is not str for key in values)
    ):
        raise PermissionDenied("Unexpected or duplicated arguments.")

    if target_field is None:
        if route_target is not None:
            raise PermissionDenied("Request creation has no route target.")
    elif type(route_target) is not UUID or not route_target.int:
        raise PermissionDenied("A trusted route target is required.")

    if command.action in ("surrender", "revoke"):
        required_kind = (
            "VOLUNTARY_SURRENDER" if command.action == "surrender"
            else "ADMINISTRATIVE_REVOCATION"
        )
        if values["kind"] != required_kind:
            raise PermissionDenied("Termination kind conflicts with action.")

    values[actor_field] = command.actor_id
    if target_field is not None:
        values[target_field] = route_target

    return DelegationServicePlan(
        operation=operation,
        arguments=tuple(sorted(values.items())),
    )


def execute_service_plan(*args, **kwargs):
    raise PermissionDenied("Operational delegation dispatch is disabled.")