"""Unregistered, read-only serial-exception approval candidate verification.

Returns evidence status only, never actual exception effectiveness,
installation authorization, or permission to bypass serial capture.
"""
from dataclasses import dataclass
from uuid import UUID

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_serial_exception_service import (
    REQUEST_KIND, DECISION_KIND, REVOCATION_KIND,
)
from .models import Project, ProjectEvidence


@dataclass(frozen=True)
class SerialExceptionCandidate:
    msr_id: str
    unit_id: str
    approval_candidate_verified: bool
    blockers: tuple[str, ...]
    exception_effective: bool = False
    installation_authorized: bool = False


def verify_serial_exception_candidate(*, project_id, msr_id, unit_id):
    """Inspect current records without inserting or updating anything."""
    try:
        requested_msr = str(UUID(str(msr_id)))
        UUID(str(project_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Valid project and MSR identifiers are required.") from None

    if type(unit_id) is not str or not unit_id.strip():
        raise ValueError("A physical unit identifier is required.")

    blockers = []

    def blocked(message):
        return SerialExceptionCandidate(
            msr_id=requested_msr,
            unit_id=unit_id,
            approval_candidate_verified=False,
            blockers=(message,),
        )

    project = Project.objects.filter(pk=project_id).select_related(
        "current_approved"
    ).first()

    if project is None:
        return blocked("Project does not exist.")

    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or str(msr.pk) != requested_msr
        or msr.project_id != project.pk
    ):
        return blocked("Current approved MSR does not match.")

    try:
        units = physical_units_from_snapshot(
            msr_id=str(msr.pk), snapshot=msr.snapshot
        )
    except ValueError:
        return blocked("Equipment snapshot is not valid for identification.")

    if unit_id not in {item.unit_id for item in units}:
        return blocked("Physical unit is not in this approved MSR.")

    snapshot_digest = canonical_hash(msr.snapshot)

    requests = list(ProjectEvidence.objects.filter(
        msr=msr, kind=REQUEST_KIND
    ))
    matching_requests = [
        item for item in requests if item.data.get("unit_id") == unit_id
    ]

    if len(matching_requests) != 1:
        return blocked("Exactly one request for this unit is required.")

    request = matching_requests[0]
    r = request.data

    if (
        canonical_hash(r) != request.digest
        or r.get("status") != "REQUESTED"
        or r.get("msr_id") != str(msr.pk)
        or r.get("msr_version") != msr.number
        or r.get("snapshot_sha256") != snapshot_digest
        or r.get("unit_id") != unit_id
        or r.get("requester_id") != str(request.created_by_id)
        or r.get("comptroller_approved") is not False
        or r.get("exception_effective") is not False
        or r.get("installation_authorized") is not False
    ):
        return blocked("Request evidence failed integrity checks.")

    decisions = list(ProjectEvidence.objects.filter(
        msr=msr, kind=DECISION_KIND
    ))
    matching_decisions = [
        item for item in decisions
        if item.data.get("request_id") == str(request.pk)
        or item.data.get("unit_id") == unit_id
    ]

    if len(matching_decisions) != 1:
        return blocked("Exactly one matching decision is required.")

    decision = matching_decisions[0]
    d = decision.data

    if (
        canonical_hash(d) != decision.digest
        or d.get("status") != "APPROVED"
        or d.get("comptroller_approved") is not True
        or d.get("genuinely_not_applicable") is not True
        or d.get("request_id") != str(request.pk)
        or d.get("request_digest") != request.digest
        or d.get("msr_id") != str(msr.pk)
        or d.get("msr_version") != msr.number
        or d.get("snapshot_sha256") != snapshot_digest
        or d.get("unit_id") != unit_id
        or d.get("requester_id") != str(request.created_by_id)
        or d.get("comptroller_id") != str(decision.created_by_id)
        or decision.created_by_id == request.created_by_id
        or d.get("exception_effective") is not False
        or d.get("installation_authorized") is not False
    ):
        return blocked("Comptroller approval evidence is invalid or rejected.")

    # Fail closed on any revocation referencing the decision or unit.
    # A damaged or ambiguous revocation must never be silently ignored.
    revocations = list(ProjectEvidence.objects.filter(
        msr=msr, kind=REVOCATION_KIND
    ))
    related_revocations = [
        item for item in revocations
        if item.data.get("decision_id") == str(decision.pk)
        or item.data.get("unit_id") == unit_id
    ]

    if related_revocations:
        for revocation in related_revocations:
            v = revocation.data
            if (
                canonical_hash(v) != revocation.digest
                or v.get("decision_id") != str(decision.pk)
                or v.get("decision_digest") != decision.digest
                or v.get("unit_id") != unit_id
                or v.get("msr_id") != str(msr.pk)
                or v.get("snapshot_sha256") != snapshot_digest
                or v.get("status") != "REVOKED"
            ):
                blockers.append("Revocation evidence integrity is uncertain.")
            else:
                blockers.append("Comptroller approval has been revoked.")

    return SerialExceptionCandidate(
        msr_id=requested_msr,
        unit_id=unit_id,
        approval_candidate_verified=not blockers,
        blockers=tuple(blockers),
    )