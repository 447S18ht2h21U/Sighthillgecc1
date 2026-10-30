"""Proposed permission revocation and expiration policy.

Pure decision helpers only. These functions cannot write records,
revoke active permissions, or authorize live access.

Existing temporary-duty and project-access authorization rules
remain unchanged.
"""

from datetime import datetime

from .access_user_permission_grant_policy import (
    APPROVED,
    EXPIRED,
    REVOKED,
)


VOLUNTARY_SURRENDER = "VOLUNTARY_SURRENDER"
ADMINISTRATIVE_REVOCATION = "ADMINISTRATIVE_REVOCATION"


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def proposed_permission_surrender_allowed(
    *,
    status,
    recipient_id,
    actor_id,
    actor_authenticated,
    actor_active,
    reason,
):
    """Evaluate voluntary surrender without changing authorization."""

    return (
        status == APPROVED
        and recipient_id is not None
        and actor_id == recipient_id
        and actor_authenticated is True
        and actor_active is True
        and isinstance(reason, str)
        and bool(reason.strip())
    )


def proposed_administrative_revocation_allowed(
    *,
    status,
    recipient_id,
    requested_by_id,
    actor_id,
    actor_authenticated,
    actor_active,
    independently_authorized,
    reason,
):
    """Require explicit independent revocation authority."""

    return (
        status == APPROVED
        and recipient_id is not None
        and requested_by_id is not None
        and actor_id is not None
        and actor_id != recipient_id
        and actor_id != requested_by_id
        and actor_authenticated is True
        and actor_active is True
        and independently_authorized is True
        and isinstance(reason, str)
        and bool(reason.strip())
    )


def proposed_permission_is_time_expired(
    *,
    status,
    ends_at,
    now,
):
    """Determine when approved permission eligibility has ended."""

    if status != APPROVED:
        return False

    if not _aware(ends_at) or not _aware(now):
        return False

    return now >= ends_at


def proposed_permission_effective_at(
    *,
    status,
    starts_at,
    ends_at,
    now,
    recipient_active,
):
    """Describe time and recipient eligibility, not live authorization."""

    if status in {REVOKED, EXPIRED}:
        return False

    if status != APPROVED or recipient_active is not True:
        return False

    if not all(_aware(value) for value in (starts_at, ends_at, now)):
        return False

    return starts_at <= now < ends_at


def permission_revocation_executed(*args, **kwargs):
    """No operational revocation until approved audited integration."""

    return False