"""Unregistered read-only inspection candidate verification.

Never creates trusted evidence or grants installation authority.
"""
from dataclasses import dataclass
from uuid import UUID

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_capture_pending_service import KIND as PENDING_KIND
from .equipment_physical_inspection_review_service import REVIEW_KIND
from .models import Project, ProjectEvidence


@dataclass(frozen=True)
class InspectionVerification:
    msr_id: str
    unit_id: str
    review_candidate_verified: bool
    blockers: tuple[str, ...]
    trusted_installation_evidence: bool = False
    installation_authorized: bool = False


def verify_physical_inspection_candidate(*, project_id, msr_id, unit_id):
    try:
        project_key = str(UUID(str(project_id)))
        msr_key = str(UUID(str(msr_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Valid project and MSR identifiers required.") from None

    if type(unit_id) is not str or not unit_id.strip():
        raise ValueError("Specific physical unit required.")

    def denied(message):
        return InspectionVerification(
            msr_id=msr_key,
            unit_id=unit_id,
            review_candidate_verified=False,
            blockers=(message,),
        )

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_key).first()

    if project is None or project.state == "CANCELLED":
        return denied("Active project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or str(msr.pk) != msr_key
        or str(msr.project_id) != project_key
    ):
        return denied("Current approved MSR does not match.")

    try:
        units = physical_units_from_snapshot(
            msr_id=msr_key, snapshot=msr.snapshot
        )
    except (ValueError, TypeError):
        return denied("Approved equipment snapshot invalid.")

    if unit_id not in {unit.unit_id for unit in units}:
        return denied("Unit absent from approved MSR.")

    snapshot_hash = canonical_hash(msr.snapshot)

    captures = list(ProjectEvidence.objects.filter(
        msr=msr, kind=PENDING_KIND
    ))
    if any(type(record.data) is not dict for record in captures):
        return denied("Malformed physical inspection history.")

    matched = [
        record for record in captures
        if record.data.get("unit_id") == unit_id
    ]
    if len(matched) != 1:
        return denied("Exactly one unit capture required.")

    pending = matched[0]
    p = pending.data

    if (
        pending.digest != canonical_hash(p)
        or p.get("purpose") != "PHYSICAL_INSPECTION_PENDING_VERIFICATION"
        or p.get("project_id") != project_key
        or p.get("msr_id") != msr_key
        or p.get("msr_version") != msr.number
        or p.get("snapshot_sha256") != snapshot_hash
        or p.get("unit_id") != unit_id
        or p.get("recorded_by") != str(pending.created_by_id)
        or p.get("confirmed_in_person") is not True
        or p.get("independently_verified") is not False
        or p.get("trusted_installation_evidence") is not False
        or p.get("installation_authorized") is not False
        or type(p.get("serial_number")) is not str
        or not p["serial_number"].strip()
    ):
        return denied("Capture evidence integrity failed.")

    decisions = list(ProjectEvidence.objects.filter(
        msr=msr, kind=REVIEW_KIND
    ))
    if any(type(record.data) is not dict for record in decisions):
        return denied("Malformed independent review history.")

    matched_decisions = [
        record for record in decisions
        if (
            record.data.get("pending_id") == str(pending.pk)
            or record.data.get("unit_id") == unit_id
        )
    ]
    if len(matched_decisions) != 1:
        return denied("Exactly one independent review required.")

    review = matched_decisions[0]
    d = review.data

    if (
        review.digest != canonical_hash(d)
        or d.get("status") != "CANDIDATE_ACCEPTED"
        or d.get("pending_id") != str(pending.pk)
        or d.get("pending_digest") != pending.digest
        or d.get("project_id") != project_key
        or d.get("msr_id") != msr_key
        or d.get("msr_version") != msr.number
        or d.get("snapshot_sha256") != snapshot_hash
        or d.get("unit_id") != unit_id
        or d.get("recorder_id") != str(pending.created_by_id)
        or d.get("reviewer_id") != str(review.created_by_id)
        or review.created_by_id == pending.created_by_id
        or d.get("independently_examined") is not True
        or d.get("trusted_installation_evidence") is not False
        or d.get("installation_authorized") is not False
    ):
        return denied("Independent review rejected or invalid.")

    return InspectionVerification(
        msr_id=msr_key,
        unit_id=unit_id,
        review_candidate_verified=True,
        blockers=(),
    )