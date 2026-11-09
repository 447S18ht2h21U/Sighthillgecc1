"""Non-operational immutable evidence design for MSR viewing delegation.

These records are in-memory design structures. They do not create Django
models, migrations, permissions, audit records, or API access.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class MSRDelegationRequestEvidence:
    request_id: UUID
    recipient_id: UUID
    requested_by_id: UUID
    source_associate_id: UUID
    project_ids: tuple[UUID, ...]
    requested_at: datetime
    starts_at: datetime
    ends_at: datetime
    reason: str


@dataclass(frozen=True)
class MSRDelegationDecisionEvidence:
    decision_id: UUID
    request_id: UUID
    decided_by_id: UUID
    decision: str
    decided_at: datetime
    reason: str
    authority_reference: str


@dataclass(frozen=True)
class MSRDelegationTerminationEvidence:
    termination_id: UUID
    decision_id: UUID
    terminated_by_id: UUID | None
    termination_kind: str
    terminated_at: datetime
    reason: str
    authority_reference: str


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
    if not isinstance(record, MSRDelegationRequestEvidence):
        return False
    identities = (
        record.request_id,
        record.recipient_id,
        record.requested_by_id,
        record.source_associate_id,
    )
    return (
        all(isinstance(value, UUID) for value in identities)
        and isinstance(record.project_ids, tuple)
        and 1 <= len(record.project_ids) <= 100
        and all(isinstance(value, UUID) for value in record.project_ids)
        and len(set(record.project_ids)) == len(record.project_ids)
        and record.recipient_id != record.source_associate_id
        and _aware(record.requested_at)
        and _aware(record.starts_at)
        and _aware(record.ends_at)
        and record.requested_at <= record.ends_at
        and record.starts_at < record.ends_at
        and isinstance(record.reason, str)
        and 10 <= len(record.reason.strip()) <= 2000
    )


def valid_decision_evidence(request, decision):
    if not valid_request_evidence(request):
        return False
    if not isinstance(decision, MSRDelegationDecisionEvidence):
        return False
    return (
        isinstance(decision.decision_id, UUID)
        and decision.request_id == request.request_id
        and isinstance(decision.decided_by_id, UUID)
        and decision.decided_by_id not in {
            request.recipient_id,
            request.requested_by_id,
        }
        and decision.decision in DECISIONS
        and _aware(decision.decided_at)
        and request.requested_at <= decision.decided_at
        and decision.decided_at < request.ends_at
        and isinstance(decision.reason, str)
        and bool(decision.reason.strip())
        and isinstance(decision.authority_reference, str)
        and bool(decision.authority_reference.strip())
    )


def valid_termination_evidence(request, decision, termination):
    if not valid_decision_evidence(request, decision):
        return False
    if decision.decision != "APPROVED":
        return False
    if not isinstance(termination, MSRDelegationTerminationEvidence):
        return False
    if termination.decision_id != decision.decision_id:
        return False
    if not isinstance(termination.termination_id, UUID):
        return False
    if termination.termination_kind not in TERMINATIONS:
        return False
    if not _aware(termination.terminated_at):
        return False
    if termination.terminated_at < decision.decided_at:
        return False
    if not isinstance(termination.reason, str):
        return False
    if not termination.reason.strip():
        return False

    if termination.termination_kind == "AUTOMATIC_EXPIRATION":
        return (
            termination.terminated_by_id is None
            and termination.terminated_at >= request.ends_at
        )

    if not isinstance(termination.terminated_by_id, UUID):
        return False

    if termination.termination_kind == "VOLUNTARY_SURRENDER":
        return termination.terminated_by_id == request.recipient_id

    return (
        termination.termination_kind == "ADMINISTRATIVE_REVOCATION"
        and isinstance(termination.authority_reference, str)
        and bool(termination.authority_reference.strip())
    )


def proposed_delegation_is_current(
    request, decision, *, now, recipient_active, termination=None
):
    """Evaluate a proposed state, never grant operational API access."""
    if not valid_decision_evidence(request, decision):
        return False
    if decision.decision != "APPROVED":
        return False
    if termination is not None:
        if not valid_termination_evidence(request, decision, termination):
            return False
        if termination.terminated_at <= now:
            return False
    return (
        recipient_active is True
        and _aware(now)
        and decision.decided_at <= now
        and request.starts_at <= now < request.ends_at
    )


def immutable_evidence_grants_access(*args, **kwargs):
    """Only future trusted persistence integration can authorize reads."""
    return False