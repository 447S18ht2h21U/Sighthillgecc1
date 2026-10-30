"""Non-executable coordination of VERIDIAN permission termination rules.

Voluntary surrender, administrative revocation, and time expiration
have different authority requirements.

This module creates no access grants, revocations, audit records,
database writes, or API endpoints.
"""

from .access_user_permission_grant_policy import APPROVED
from .access_user_permission_grant_transitions import transition_is_allowed
from .access_user_permission_revocation_policy import (
    proposed_administrative_revocation_allowed,
    proposed_permission_is_time_expired,
    proposed_permission_surrender_allowed,
)


SURRENDER = "VOLUNTARY_SURRENDER"
ADMINISTRATIVE = "ADMINISTRATIVE_REVOCATION"
EXPIRATION = "AUTOMATIC_EXPIRATION"


def proposed_termination_allowed(
    *,
    action,
    status,
    recipient_id,
    requested_by_id,
    actor_id,
    actor_authenticated,
    actor_active,
    independently_authorized,
    reason,
    starts_at,
    ends_at,
    now,
):
    """Evaluate termination eligibility, never execute a transition."""

    if status != APPROVED:
        return False

    if action == SURRENDER:
        return proposed_permission_surrender_allowed(
            status=status,
            recipient_id=recipient_id,
            actor_id=actor_id,
            actor_authenticated=actor_authenticated,
            actor_active=actor_active,
            reason=reason,
        )

    if action == ADMINISTRATIVE:
        authorized = proposed_administrative_revocation_allowed(
            status=status,
            recipient_id=recipient_id,
            requested_by_id=requested_by_id,
            actor_id=actor_id,
            actor_authenticated=actor_authenticated,
            actor_active=actor_active,
            independently_authorized=independently_authorized,
            reason=reason,
        )

        return authorized and transition_is_allowed(
            status,
            "REVOKED",
            recipient_id=recipient_id,
            requested_by_id=requested_by_id,
            decision_actor_id=actor_id,
            decision_actor_active=actor_active,
            decision_at=now,
            starts_at=starts_at,
            ends_at=ends_at,
        )

    if action == EXPIRATION:
        return proposed_permission_is_time_expired(
            status=status,
            ends_at=ends_at,
            now=now,
        )

    return False


def permission_termination_executed(*args, **kwargs):
    """No live termination before audited authorization integration."""

    return False