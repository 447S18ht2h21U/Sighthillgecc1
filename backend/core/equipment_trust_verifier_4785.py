"""Independent read-side verification of equipment adjudication.

An approved, verified decision is not a trusted installation record
and never grants installation, Receipt issuance, delivery or completion.
Operational approval policy remains provisional.
"""

from dataclasses import dataclass

from .documents import canonical_hash
from .equipment_trust_decision_4784 import KIND
from .receipt_equipment_manifest_4768 import build_receipt_equipment_manifest
from .models import ProjectEvidence, Role, User


@dataclass(frozen=True)
class EquipmentDecisionVerification:
    project_id: str
    msr_id: str
    expected_units: int
    approved_decisions_verified: int
    rejected_decisions_verified: int
    blockers: tuple[str, ...]
    all_approval_decisions_verified: bool
    trusted_installation_evidence: bool = False
    installation_authorized: bool = False
    receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def verify_equipment_trust_decisions(project):
    """Evaluate immutable decision history and exact source bindings."""
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)

    if (
        msr is None
        or getattr(msr, "status", None) != "APPROVED"
        or str(getattr(msr, "project_id", "")) != str(project.pk)
    ):
        raise ValueError("Current approved MSR required.")

    manifest = build_receipt_equipment_manifest(project)
    project_id = str(project.pk)
    msr_id = str(msr.pk)
    snapshot_digest = canonical_hash(msr.snapshot)

    if (
        manifest.project_id != project_id
        or manifest.msr_id != msr_id
        or manifest.msr_version != msr.number
        or manifest.snapshot_sha256 != snapshot_digest
        or manifest.all_candidates_reviewed is not True
        or manifest.blockers
        or manifest.expected_units < 1
        or len(manifest.reviewed_units) != manifest.expected_units
        or manifest.trusted_installation_evidence is not False
        or manifest.receipt_retention_authorized is not False
        or manifest.receipt_issuance_authorized is not False
        or manifest.completion_authorized is not False
    ):
        raise ValueError("Independent equipment manifest incomplete.")

    units = {unit.unit_id: unit for unit in manifest.reviewed_units}

    if len(units) != manifest.expected_units:
        raise ValueError("Duplicate physical equipment identity.")

    decisions = list(ProjectEvidence.objects.filter(msr=msr, kind=KIND))

    if len(decisions) > manifest.expected_units:
        raise ValueError("Unexpected number of equipment decisions.")

    by_unit = {}

    for record in decisions:
        data = record.data

        if type(data) is not dict:
            raise ValueError("Malformed adjudication history.")

        unit_id = data.get("unit_id")

        if unit_id not in units or unit_id in by_unit:
            raise ValueError("Duplicate or unexpected adjudication.")

        by_unit[unit_id] = record

    approved = 0
    rejected = 0
    blockers = []

    for unit_id, unit in units.items():
        record = by_unit.get(unit_id)

        if record is None:
            blockers.append(f"Unit {unit_id}: CEO adjudication missing.")
            continue

        data = record.data

        if (
            record.digest != canonical_hash(data)
            or data.get("purpose")
                != "INDEPENDENT_EQUIPMENT_TRUST_ADJUDICATION"
            or data.get("project_id") != project_id
            or data.get("msr_id") != msr_id
            or data.get("msr_version") != msr.number
            or data.get("snapshot_sha256") != snapshot_digest
            or data.get("unit_id") != unit_id
            or data.get("serial_number") != unit.serial_number
            or data.get("pending_id") != unit.pending_evidence_id
            or data.get("pending_digest") != unit.pending_digest
            or data.get("review_id") != unit.review_evidence_id
            or data.get("review_digest") != unit.review_digest
            or data.get("decision_actor_id") != str(record.created_by_id)
            or data.get("decision") not in ("APPROVED", "REJECTED")
            or type(data.get("decision_reason")) is not str
            or not 15 <= len(data["decision_reason"].strip()) <= 2000
            or type(data.get("decided_at")) is not str
            or not data["decided_at"].strip()
            or data.get("trusted_installation_evidence") is not False
            or data.get("installation_authorized") is not False
            or data.get("receipt_issuance_authorized") is not False
            or data.get("customer_delivery_verified") is not False
            or data.get("completion_authorized") is not False
        ):
            raise ValueError("Adjudication fingerprint or binding invalid.")

        linked = list(ProjectEvidence.objects.filter(
            pk__in=(unit.pending_evidence_id, unit.review_evidence_id),
            msr=msr,
        ))

        if len(linked) != 2:
            raise ValueError("Source physical inspection records missing.")

        sources = {str(item.pk): item for item in linked}
        pending = sources.get(unit.pending_evidence_id)
        review = sources.get(unit.review_evidence_id)

        if (
            pending is None
            or review is None
            or pending.kind != "PHYSICAL_UNIT_CAPTURE_PENDING"
            or review.kind != "PHYSICAL_INSPECTION_REVIEW"
            or type(pending.data) is not dict
            or type(review.data) is not dict
            or pending.digest != canonical_hash(pending.data)
            or review.digest != canonical_hash(review.data)
            or pending.digest != unit.pending_digest
            or review.digest != unit.review_digest
            or str(pending.created_by_id) != data.get("recorder_id")
            or str(review.created_by_id) != data.get("reviewer_id")
            or pending.data.get("unit_id") != unit_id
            or review.data.get("unit_id") != unit_id
            or pending.data.get("serial_number") != unit.serial_number
            or review.data.get("pending_id") != str(pending.pk)
            or review.data.get("pending_digest") != pending.digest
            or review.data.get("status") != "CANDIDATE_ACCEPTED"
            or review.data.get("independently_examined") is not True
        ):
            raise ValueError("Physical source evidence changed or invalid.")

        actor_ids = (
            pending.created_by_id,
            review.created_by_id,
            record.created_by_id,
        )

        if len(set(actor_ids)) != 3:
            raise ValueError("Recorder, reviewer and decider must differ.")

        actors = list(User.objects.filter(pk__in=actor_ids))
        roles = {actor.pk: actor.role for actor in actors}

        if (
            len(roles) != 3
            or roles.get(pending.created_by_id) != Role.INSTALLATION_MANAGER
            or roles.get(review.created_by_id) != Role.COMPTROLLER
            or roles.get(record.created_by_id) != Role.CEO
        ):
            raise ValueError("Independent authorization roles invalid.")

        if data["decision"] == "APPROVED":
            approved += 1
        else:
            rejected += 1
            blockers.append(f"Unit {unit_id}: CEO adjudication rejected.")

    if approved != manifest.expected_units:
        blockers.append("All units require verified affirmative adjudication.")

    return EquipmentDecisionVerification(
        project_id=project_id,
        msr_id=msr_id,
        expected_units=manifest.expected_units,
        approved_decisions_verified=approved,
        rejected_decisions_verified=rejected,
        blockers=tuple(dict.fromkeys(blockers)),
        all_approval_decisions_verified=(
            approved == manifest.expected_units and not blockers
        ),
    )
