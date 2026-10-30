"""Non-executable individual user permission request validation.

No persistence, approval, account modification, or access activation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from .access_permission_scope_drafts import validate_permission_scope_draft


@dataclass(frozen=True)
class UserPermissionRequestDraft:
    recipient_id: uuid.UUID
    requester_id: uuid.UUID
    permission_code: str
    scope: str
    project_ids: tuple[uuid.UUID, ...]
    starts_at: datetime
    ends_at: datetime
    reason: str
    requires_independent_approval: bool


def _identity(value):
    if not isinstance(value, (uuid.UUID, str)):
        raise ValueError("User identity must be a UUID.")
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid user identity.") from exc


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def validate_user_permission_request_draft(
    *,
    recipient_id,
    requester_id,
    permission_code,
    scope,
    starts_at,
    ends_at,
    reason,
    project_ids=(),
):
    """Validate a proposed request; do not grant permission."""

    recipient = _identity(recipient_id)
    requester = _identity(requester_id)

    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
        raise ValueError("A reason of 10 to 2000 characters is required.")

    if not _aware(starts_at) or not _aware(ends_at):
        raise ValueError("Effective dates must include a timezone.")

    if starts_at >= ends_at:
        raise ValueError("Permission end date must follow start date.")

    scope_draft = validate_permission_scope_draft(
        permission_code, scope, project_ids
    )

    return UserPermissionRequestDraft(
        recipient_id=recipient,
        requester_id=requester,
        permission_code=scope_draft.permission_code,
        scope=scope_draft.scope,
        project_ids=scope_draft.project_ids,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason.strip(),
        requires_independent_approval=scope_draft.requires_independent_approval,
    )


def request_draft_grants_access(*args, **kwargs):
    """Draft requests never constitute active system authorization."""
    return False