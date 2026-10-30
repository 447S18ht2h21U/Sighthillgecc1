"""Proposed lifecycle rules for VERIDIAN user permission grants.

Pure policy functions only. No database changes, access grants,
approval operations, or API endpoints are implemented here.
"""

from datetime import datetime

from .access_user_permission_grant_policy import (
    APPROVED,
    EXPIRED,
    REJECTED,
    REQUESTED,
    REVOKED,
)


ALLOWED_TRANSITIONS = {
    REQUESTED: frozenset({APPROVED, REJECTED}),
    APPROVED: frozenset({REVOKED, EXPIRED}),
    REJECTED: frozenset(),
    REVOKED: frozenset(),
    EXPIRED: frozenset(),
}


def transition_is_allowed(
    current_status,
    target_status,
    *,
    recipient_id,
    requested_by_id,
    decision_actor_id,
    decision_actor_active,
    decision_at,
    starts_at,
    ends_at,
):
    """Validate a proposed transition without performing it."""

    if target_status not in ALLOWED_TRANSITIONS.get(
        current_status, frozenset()
    ):
        return False

    if (
        recipient_id is None
        or requested_by_id is None
        or decision_actor_id is None
    ):
        return False

    if decision_actor_active is not True:
        return False

    if decision_actor_id in {recipient_id, requested_by_id}:
        return False

    if not isinstance(decision_at, datetime):
        return False

    if decision_at.tzinfo is None or decision_at.utcoffset() is None:
        return False

    if (
        not isinstance(starts_at, datetime)
        or not isinstance(ends_at, datetime)
    ):
        return False

    if (
        starts_at.tzinfo is None
        or starts_at.utcoffset() is None
        or ends_at.tzinfo is None
        or ends_at.utcoffset() is None
    ):
        return False

    if starts_at >= ends_at:
        return False

    if current_status == REQUESTED:
        return target_status in {APPROVED, REJECTED}

    if current_status == APPROVED:
        if target_status == EXPIRED:
            return decision_at >= ends_at

        if target_status == REVOKED:
            return decision_at < ends_at

    return False


def permission_transition_executed(*args, **kwargs):
    """Transitions cannot execute before approved service integration."""

    return False