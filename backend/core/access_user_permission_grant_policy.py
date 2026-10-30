"""Proposed user-permission authorization policy for VERIDIAN.

Pure policy evaluation only. This module does not create, approve,
persist, or activate permission grants.

Current operational authorization remains default-deny.
"""

from datetime import datetime

from .access_permission_catalog import PERMISSION_BY_CODE


REQUESTED = "REQUESTED"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
REVOKED = "REVOKED"
EXPIRED = "EXPIRED"

VALID_STATES = frozenset({
    REQUESTED,
    APPROVED,
    REJECTED,
    REVOKED,
    EXPIRED,
})


def proposed_grant_is_well_formed(
    *,
    permission_code,
    recipient_id,
    requested_by_id,
    approved_by_id,
    status,
    starts_at,
    ends_at,
    decided_at,
    revoked_at=None,
):
    """Validate proposed evidence without authorizing access."""

    if permission_code not in PERMISSION_BY_CODE:
        return False

    identities = (recipient_id, requested_by_id)

    if any(identity is None for identity in identities):
        return False


    if status not in VALID_STATES:
        return False

    times = (starts_at, ends_at)

    if any(not isinstance(value, datetime) for value in times):
        return False

    if any(value.tzinfo is None or value.utcoffset() is None for value in times):
        return False

    if starts_at >= ends_at:
        return False

    if status == REQUESTED:
        return (
            approved_by_id is None
            and decided_at is None
            and revoked_at is None
        )

    if not isinstance(decided_at, datetime):
        return False

    if decided_at.tzinfo is None or decided_at.utcoffset() is None:
        return False

    if status == APPROVED:
        return (
            approved_by_id is not None
            and approved_by_id != recipient_id
            and approved_by_id != requested_by_id
            and revoked_at is None
        )

    if status == REJECTED:
        return (
            approved_by_id is not None
            and approved_by_id != recipient_id
            and approved_by_id != requested_by_id
            and revoked_at is None
        )

    if status == REVOKED:
        return (
            approved_by_id is not None
            and approved_by_id != recipient_id
            and approved_by_id != requested_by_id
            and isinstance(revoked_at, datetime)
            and revoked_at.tzinfo is not None
            and revoked_at.utcoffset() is not None
            and revoked_at >= decided_at
        )

    if status == EXPIRED:
        return (
            approved_by_id is not None
            and approved_by_id != recipient_id
            and approved_by_id != requested_by_id
            and revoked_at is None
        )

    return False


def proposed_grant_is_current(
    *,
    valid_grant,
    status,
    starts_at,
    ends_at,
    now,
    recipient_active,
    approver_active,
):
    """Describe eligibility only; never return an effective access grant."""

    if valid_grant is not True:
        return False

    if status != APPROVED:
        return False

    if recipient_active is not True:
        return False

    # Approval authority is established when the decision is issued.
    # The original approver's later account status must not invalidate
    # otherwise valid historical approval evidence.
    # Retain approver_active in the signature for existing callers.

    if not isinstance(now, datetime):
        return False

    if now.tzinfo is None or now.utcoffset() is None:
        return False

    try:
        return starts_at <= now < ends_at
    except (TypeError, ValueError):
        return False


def permission_access_granted_by_policy(*args, **kwargs):
    """No live authorization until model, approval, and audit integration."""

    return False