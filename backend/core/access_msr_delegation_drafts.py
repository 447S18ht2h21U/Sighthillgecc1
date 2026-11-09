"""Non-operational, fixed-scope MSR viewing delegation design.

This module does not create permissions, alter ownership, connect to the
database, or authorize access through the registered MSR endpoint.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .models import Role


@dataclass(frozen=True)
class MSRDelegationDraft:
    manager_id: UUID
    recipient_id: UUID
    source_associate_id: UUID
    project_ids: tuple[UUID, ...]
    starts_at: datetime
    ends_at: datetime
    reason: str
    read_only: bool = True


def _identity(value):
    try:
        if not isinstance(value, (UUID, str)):
            return None
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def validate_msr_delegation_draft(
    *,
    manager_id,
    manager_role,
    manager_active,
    recipient_id,
    recipient_role,
    recipient_active,
    source_associate_id,
    source_associate_role,
    source_associate_active,
    project_ids,
    starts_at,
    ends_at,
    reason,
):
    """Validate proposed evidence only; grant no operational authority."""

    if manager_role != Role.SALES_MANAGER or manager_active is not True:
        raise ValueError("An active Sales Manager is required.")

    if recipient_role != Role.SALES_ASSOCIATE or recipient_active is not True:
        raise ValueError("An active Sales Associate recipient is required.")

    if source_associate_role != Role.SALES_ASSOCIATE:
        raise ValueError("The source must be a Sales Associate.")

    manager = _identity(manager_id)
    recipient = _identity(recipient_id)
    source = _identity(source_associate_id)

    if None in (manager, recipient, source):
        raise ValueError("Valid user identities are required.")

    if len({manager, recipient, source}) != 3:
        raise ValueError("Manager, recipient, and source must be different.")

    if source_associate_active not in (True, False):
        raise ValueError("The source account state must be explicit.")

    if not isinstance(project_ids, (tuple, list)):
        raise ValueError("Projects must be explicitly selected.")

    if not 1 <= len(project_ids) <= 100:
        raise ValueError("Select between 1 and 100 projects.")

    normalized = tuple(_identity(value) for value in project_ids)

    if any(value is None for value in normalized):
        raise ValueError("A project identifier is invalid.")

    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate project identifiers are prohibited.")

    if not _aware(starts_at) or not _aware(ends_at):
        raise ValueError("Delegation dates must include timezone information.")

    if starts_at >= ends_at:
        raise ValueError("The expiration must follow the start time.")

    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
        raise ValueError("A documented reason of 10 to 2000 characters is required.")

    return MSRDelegationDraft(
        manager_id=manager,
        recipient_id=recipient,
        source_associate_id=source,
        project_ids=normalized,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason.strip(),
    )


def msr_delegation_draft_grants_access(*args, **kwargs):
    """Live delegation remains disabled until approved integration."""
    return False


def msr_delegation_draft_grants_write(*args, **kwargs):
    return False


def msr_delegation_draft_grants_signing(*args, **kwargs):
    return False


def msr_delegation_draft_grants_financial_access(*args, **kwargs):
    return False