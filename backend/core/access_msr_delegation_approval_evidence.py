"""Non-operational approval evidence for fixed-scope MSR delegation.

No database models, records, permissions, or API integrations are created.
Evidence validation is not proof of trusted approval authority.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


REQUESTED = "REQUESTED"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
REVOKED = "REVOKED"
EXPIRED = "EXPIRED"

STATES = frozenset({
    REQUESTED, APPROVED, REJECTED, REVOKED, EXPIRED,
})


@dataclass(frozen=True)
class MSRDelegationApprovalEvidence:
    request_id: UUID
    recipient_id: UUID
    requested_by_id: UUID
    approved_by_id: UUID | None
    project_ids: tuple[UUID, ...]
    starts_at: datetime
    ends_at: datetime
    status: str
    decided_at: datetime | None
    revoked_at: datetime | None = None


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def validate_approval_evidence(evidence):
    """Validate immutable-style evidence shape, never activate access."""

    if not isinstance(evidence, MSRDelegationApprovalEvidence):
        return False

    if not all(
        isinstance(value, UUID)
        for value in (
            evidence.request_id,
            evidence.recipient_id,
            evidence.requested_by_id,
        )
    ):
        return False

    if evidence.status not in STATES:
        return False

    if not _aware(evidence.starts_at) or not _aware(evidence.ends_at):
        return False

    if evidence.starts_at >= evidence.ends_at:
        return False

    if not isinstance(evidence.project_ids, tuple):
        return False

    if not 1 <= len(evidence.project_ids) <= 100:
        return False

    if not all(isinstance(value, UUID) for value in evidence.project_ids):
        return False

    if len(set(evidence.project_ids)) != len(evidence.project_ids):
        return False

    if evidence.status == REQUESTED:
        return (
            evidence.approved_by_id is None
            and evidence.decided_at is None
            and evidence.revoked_at is None
        )

    if not isinstance(evidence.approved_by_id, UUID):
        return False

    if evidence.approved_by_id in {
        evidence.recipient_id, evidence.requested_by_id,
    }:
        return False

    if not _aware(evidence.decided_at):
        return False

    if evidence.status in {APPROVED, REJECTED, EXPIRED}:
        return evidence.revoked_at is None

    if evidence.status == REVOKED:
        return (
            _aware(evidence.revoked_at)
            and evidence.revoked_at >= evidence.decided_at
        )

    return False


def proposed_approval_is_current(evidence, *, now, recipient_active):
    """Assess eligibility only; never return an operational grant."""

    if not validate_approval_evidence(evidence):
        return False

    return (
        evidence.status == APPROVED
        and recipient_active is True
        and _aware(now)
        and evidence.starts_at <= now < evidence.ends_at
        and evidence.decided_at <= now
    )


def msr_approval_evidence_grants_access(*args, **kwargs):
    """No live access without trusted persisted approval integration."""
    return False