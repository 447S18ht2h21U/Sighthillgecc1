"""Fail-closed API input contract for proposed MSR delegation workflows.

Not registered as an endpoint. Does not query the database, call services,
issue decisions, modify records, or grant operational MSR access.
Authenticated actor IDs must be obtained separately from trusted sessions.
"""

from datetime import datetime
from uuid import UUID


class DelegationInputError(ValueError):
    """Invalid or unexpected client-provided delegation input."""


def _object(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise DelegationInputError("Invalid request fields.")
    return value


def _uuid(value):
    if type(value) is not str:
        raise DelegationInputError("Invalid identifier.")
    try:
        result = UUID(value)
    except (ValueError, AttributeError):
        raise DelegationInputError("Invalid identifier.") from None
    if not result.int or str(result) != value:
        raise DelegationInputError("Invalid identifier.")
    return result


def _reason(value):
    if type(value) is not str or not 10 <= len(value.strip()) <= 2000:
        raise DelegationInputError("A documented reason is required.")
    return value.strip()


def _datetime(value):
    if type(value) is not str or len(value) > 40:
        raise DelegationInputError("Invalid timestamp.")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise DelegationInputError("Invalid timestamp.") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise DelegationInputError("Timezone is required.")
    return result


def parse_request_payload(value):
    """Validate inputs; the manager must come from authenticated identity."""
    _object(value, (
        "recipient_id", "source_associate_id", "project_ids",
        "starts_at", "ends_at", "reason",
    ))
    recipient = _uuid(value["recipient_id"])
    source = _uuid(value["source_associate_id"])

    projects = value["project_ids"]
    if type(projects) is not list or not 1 <= len(projects) <= 100:
        raise DelegationInputError("Invalid project selection.")

    project_ids = tuple(_uuid(item) for item in projects)
    if len(set(project_ids)) != len(project_ids):
        raise DelegationInputError("Duplicate projects are prohibited.")

    begins = _datetime(value["starts_at"])
    ends = _datetime(value["ends_at"])
    if begins >= ends:
        raise DelegationInputError("Invalid delegation date range.")

    if recipient == source:
        raise DelegationInputError("Recipient and source must differ.")

    return {
        "recipient_id": recipient,
        "source_associate_id": source,
        "project_ids": project_ids,
        "starts_at": begins,
        "ends_at": ends,
        "reason": _reason(value["reason"]),
    }


def parse_approval_payload(value):
    _object(value, ("reason",))
    return {"reason": _reason(value["reason"])}


def parse_termination_payload(value):
    _object(value, ("kind", "reason"))
    allowed = {
        "VOLUNTARY_SURRENDER",
        "ADMINISTRATIVE_REVOCATION",
    }
    if type(value["kind"]) is not str or value["kind"] not in allowed:
        raise DelegationInputError("Invalid termination kind.")
    return {
        "kind": value["kind"],
        "reason": _reason(value["reason"]),
    }


def parse_reassignment_payload(value):
    _object(value, ("new_owner_id", "reason"))
    return {
        "new_owner_id": _uuid(value["new_owner_id"]),
        "reason": _reason(value["reason"]),
    }


def api_contract_grants_live_msr_access(*args, **kwargs):
    return False