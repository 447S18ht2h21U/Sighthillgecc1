"""Fail-closed completion envelope attempt state policy; no sending."""

from rest_framework.exceptions import ValidationError

ALLOWED = {
    "AUTH_PENDING": {"CANCELLED_UNSENT"},
    "CANCELLED_UNSENT": set(),
    "NETWORK_STARTED": set(),
    "SENT_UNCHECKED": set(),
    "SEND_UNCERTAIN": set(),
}


def require_transition(current_state, next_state, first_send_started_at=None):
    """Validate an unsent cancellation only; never authorize network operations."""
    if current_state not in ALLOWED or next_state not in ALLOWED[current_state]:
        raise ValidationError("Completion envelope state transition is not permitted.")
    if first_send_started_at is not None:
        raise ValidationError("An attempt with recorded send activity cannot be cancelled as unsent.")
    return next_state
