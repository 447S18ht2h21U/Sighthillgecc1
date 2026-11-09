"""Fail-closed evaluation of a proposed fixed-project MSR delegation.

Inputs must come from freshly verified, locked database records inside
an atomic authorization transaction. Never construct these from client
parameters. This module is not wired into the operational MSR API.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


def _uuid(value):
    return type(value) is UUID and value.int != 0


def _aware(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


@dataclass(frozen=True)
class EffectiveScopeEvidence:
    request_id: UUID
    recipient_id: UUID
    project_id: UUID
    original_owner_id: UUID
    captured_revision: int
    decision_request_id: UUID
    decision_result: str
    begins_at: datetime
    ends_at: datetime
    terminated: bool
    project_invalidated: bool


def evaluate_fixed_msr_scope(
    evidence, *, recipient_id, project_id, current_owner_id,
    current_revision, now, recipient_active,
):
    """Eligibility predicate only; never grants operational access."""
    if type(evidence) is not EffectiveScopeEvidence:
        return False
    values = (
        evidence.request_id, evidence.recipient_id,
        evidence.project_id, evidence.original_owner_id,
        evidence.decision_request_id, recipient_id, project_id,
        current_owner_id,
    )
    if not all(_uuid(value) for value in values):
        return False
    if type(current_revision) is not int or current_revision < 0:
        return False
    if (
        type(evidence.captured_revision) is not int
        or evidence.captured_revision < 0
    ):
        return False
    if (
        type(recipient_active) is not bool
        or type(evidence.terminated) is not bool
        or type(evidence.project_invalidated) is not bool
    ):
        return False
    if not all(_aware(value) for value in (
        evidence.begins_at, evidence.ends_at, now,
    )):
        return False
    return (
        evidence.decision_result == "APPROVED"
        and evidence.decision_request_id == evidence.request_id
        and evidence.recipient_id == recipient_id
        and evidence.project_id == project_id
        and evidence.original_owner_id == current_owner_id
        and evidence.captured_revision == current_revision
        and evidence.begins_at <= now < evidence.ends_at
        and evidence.begins_at < evidence.ends_at
        and recipient_active
        and not evidence.terminated
        and not evidence.project_invalidated
    )


def effective_scope_grants_live_msr_access(*args, **kwargs):
    """Activation is prohibited until transactional service and API review."""
    return False