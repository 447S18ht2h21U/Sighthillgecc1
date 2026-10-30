"""Non-executable evidence design for VERIDIAN user permissions.

These schemas describe required historical evidence only.
They do not create models, migrations, permissions, or audit events.

Approval and revocation evidence must remain separately preserved.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .access_permission_catalog import PERMISSION_BY_CODE


@dataclass(frozen=True)
class PermissionRequestEvidence:
    request_id: UUID
    recipient_id: UUID
    requested_by_id: UUID
    permission_code: str
    reason: str
    requested_at: datetime
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class PermissionDecisionEvidence:
    request_id: UUID
    decision_id: UUID
    decided_by_id: UUID
    decision: str
    decided_at: datetime
    reason: str


@dataclass(frozen=True)
class PermissionTerminationEvidence:
    request_id: UUID
    termination_id: UUID
    terminated_by_id: UUID | None
    termination_kind: str
    terminated_at: datetime
    reason: str


DECISIONS = frozenset({"APPROVED", "REJECTED"})

TERMINATIONS = frozenset({
    "VOLUNTARY_SURRENDER",
    "ADMINISTRATIVE_REVOCATION",
    "AUTOMATIC_EXPIRATION",
})


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def valid_request_evidence(record):
    """Validate request structure; never authorize the request."""

    return (
        isinstance(record, PermissionRequestEvidence)
        and all(
            isinstance(value, UUID)
            for value in (
                record.request_id,
                record.recipient_id,
                record.requested_by_id,
            )
        )
        and record.permission_code in PERMISSION_BY_CODE
        and isinstance(record.reason, str)
        and bool(record.reason.strip())
        and all(
            _aware(value)
            for value in (
                record.requested_at,
                record.starts_at,
                record.ends_at,
            )
        )
        and record.starts_at < record.ends_at
    )


def valid_decision_evidence(request, decision):
    """Require a separately identified, independent decision-maker."""

    if not valid_request_evidence(request):
        return False

    if not isinstance(decision, PermissionDecisionEvidence):
        return False

    return (
        isinstance(decision.request_id, UUID)
        and decision.request_id == request.request_id
        and isinstance(decision.decision_id, UUID)
        and isinstance(decision.decided_by_id, UUID)
        and decision.decided_by_id not in {
            request.recipient_id,
            request.requested_by_id,
        }
        and decision.decision in DECISIONS
        and _aware(decision.decided_at)
        and decision.decided_at >= request.requested_at
        and isinstance(decision.reason, str)
        and bool(decision.reason.strip())
    )


def valid_termination_evidence(request, decision, termination):
    """Describe termination evidence; do not execute revocation."""

    if not valid_decision_evidence(request, decision):
        return False

    if decision.decision != "APPROVED":
        return False

    if not isinstance(termination, PermissionTerminationEvidence):
        return False

    if (
        not isinstance(termination.request_id, UUID)
        or termination.request_id != request.request_id
        or not isinstance(termination.termination_id, UUID)
        or termination.termination_kind not in TERMINATIONS
        or not _aware(termination.terminated_at)
        or termination.terminated_at < decision.decided_at
    ):
        return False

    if termination.termination_kind == "AUTOMATIC_EXPIRATION":
        return (
            termination.terminated_by_id is None
            and termination.terminated_at >= request.ends_at
            and isinstance(termination.reason, str)
            and bool(termination.reason.strip())
        )

    if not isinstance(termination.terminated_by_id, UUID):
        return False

    if termination.termination_kind == "VOLUNTARY_SURRENDER":
        if termination.terminated_by_id != request.recipient_id:
            return False

    if termination.termination_kind == "ADMINISTRATIVE_REVOCATION":
        if termination.terminated_by_id in {
            request.recipient_id,
            request.requested_by_id,
        }:
            return False

    return isinstance(termination.reason, str) and bool(
        termination.reason.strip()
    )


def permission_evidence_activates_access(*args, **kwargs):
    """Evidence alone never constitutes an effective access grant."""

    return False