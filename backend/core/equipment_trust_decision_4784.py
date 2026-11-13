"""Isolated equipment-trust decision with immutable independent evidence.

A CEO decision is separate from Installation Manager physical capture
and Comptroller review. This development-only record cannot enable
installation, customer Receipt issuance, delivery, or completion.

The CEO decision policy is provisional pending operational approval.
"""

import os
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .receipt_equipment_manifest_4768 import (
    build_receipt_equipment_manifest,
)
from .models import Project, ProjectEvidence, Role, User
from .services import audit


KIND = "EQUIPMENT_TRUST_DECISION"


@dataclass(frozen=True)
class EquipmentTrustDecisionResult:
    evidence_id: str
    project_id: str
    msr_id: str
    unit_id: str
    decision: str
    evidence_digest: str
    trusted_equipment_decision_recorded: bool
    installation_authorized: bool = False
    receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


@transaction.atomic
def record_equipment_trust_decision(
    *,
    actor,
    project_id,
    unit_id,
    approve,
    decision_reason,
):
    """Record independent CEO approval or rejection of reviewed evidence.

    A positive decision is durable evidence of the CEO's adjudication,
    but must undergo separate read-side trust verification before use.
    """
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_EQUIPMENT_TRUST_TEST_ENABLED") != "1"
    ):
        raise PermissionDenied("Equipment trust decisions are disabled.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated CEO required.")

    decision_actor = User.objects.filter(pk=actor.pk).first()

    if (
        decision_actor is None
        or decision_actor.is_active is not True
        or decision_actor.role != Role.CEO
    ):
        raise PermissionDenied("Active CEO required.")

    if type(approve) is not bool:
        raise ValidationError("Explicit trust decision required.")

    if (
        type(unit_id) is not str
        or not unit_id.strip()
        or type(decision_reason) is not str
        or not 15 <= len(decision_reason.strip()) <= 2000
    ):
        raise ValidationError("Physical unit and written reason required.")

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    manifest = build_receipt_equipment_manifest(project)

    if (
        manifest.project_id != str(project.pk)
        or manifest.msr_id != str(msr.pk)
        or manifest.msr_version != msr.number
        or manifest.snapshot_sha256 != canonical_hash(msr.snapshot)
        or manifest.all_candidates_reviewed is not True
        or manifest.blockers
        or manifest.expected_units < 1
        or len(manifest.reviewed_units) != manifest.expected_units
        or manifest.trusted_installation_evidence is not False
        or manifest.receipt_retention_authorized is not False
        or manifest.receipt_issuance_authorized is not False
        or manifest.completion_authorized is not False
    ):
        raise ValidationError("Independent equipment manifest incomplete.")

    matching = [
        unit for unit in manifest.reviewed_units
        if unit.unit_id == unit_id
    ]

    if len(matching) != 1:
        raise ValidationError("One reviewed physical unit required.")

    unit = matching[0]

    pending = ProjectEvidence.objects.filter(
        pk=unit.pending_evidence_id,
        msr=msr,
    ).first()

    review = ProjectEvidence.objects.filter(
        pk=unit.review_evidence_id,
        msr=msr,
    ).first()

    if (
        pending is None
        or review is None
        or pending.kind != "PHYSICAL_UNIT_CAPTURE_PENDING"
        or review.kind != "PHYSICAL_INSPECTION_REVIEW"
        or pending.digest != unit.pending_digest
        or review.digest != unit.review_digest
        or pending.digest != canonical_hash(pending.data)
        or review.digest != canonical_hash(review.data)
        or pending.created_by_id == review.created_by_id
        or decision_actor.pk in (
            pending.created_by_id,
            review.created_by_id,
        )
    ):
        raise ValidationError("Independent evidence chain invalid.")

    recorder = User.objects.filter(pk=pending.created_by_id).first()
    reviewer = User.objects.filter(pk=review.created_by_id).first()

    if (
        recorder is None
        or reviewer is None
        or recorder.role != Role.INSTALLATION_MANAGER
        or reviewer.role != Role.COMPTROLLER
    ):
        raise ValidationError("Required independent roles missing.")

    if (
        type(pending.data) is not dict
        or type(review.data) is not dict
        or pending.data.get("unit_id") != unit_id
        or review.data.get("unit_id") != unit_id
        or pending.data.get("serial_number") != unit.serial_number
        or review.data.get("pending_id") != str(pending.pk)
        or review.data.get("pending_digest") != pending.digest
        or review.data.get("status") != "CANDIDATE_ACCEPTED"
        or review.data.get("independently_examined") is not True
    ):
        raise ValidationError("Physical evidence bindings invalid.")

    # Preserve a single historical adjudication per physical unit.
    # A rejected decision cannot be overwritten by retrying approval.
    for prior in ProjectEvidence.objects.filter(
        msr=msr,
        kind=KIND,
    ):
        if (
            type(prior.data) is not dict
            or prior.digest != canonical_hash(prior.data)
        ):
            raise ValidationError("Existing trust history invalid.")

        if prior.data.get("unit_id") == unit_id:
            raise ValidationError("Equipment trust already adjudicated.")

    payload = {
        "purpose": "INDEPENDENT_EQUIPMENT_TRUST_ADJUDICATION",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": manifest.snapshot_sha256,
        "unit_id": unit_id,
        "serial_number": unit.serial_number,
        "pending_id": str(pending.pk),
        "pending_digest": pending.digest,
        "review_id": str(review.pk),
        "review_digest": review.digest,
        "recorder_id": str(pending.created_by_id),
        "reviewer_id": str(review.created_by_id),
        "decision_actor_id": str(decision_actor.pk),
        "decision": "APPROVED" if approve else "REJECTED",
        "decision_reason": decision_reason.strip(),
        "decided_at": timezone.now().isoformat(),
        "trusted_installation_evidence": False,
        "installation_authorized": False,
        "receipt_issuance_authorized": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }

    digest = canonical_hash(payload)

    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=KIND,
        created_by=decision_actor,
        data=payload,
        digest=digest,
    )

    audit(
        decision_actor,
        "equipment.trust_decision_recorded",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "msr_id": str(msr.pk),
            "unit_id": unit_id,
            "decision": payload["decision"],
            "digest": digest,
            "installation_authorized": False,
            "receipt_issuance_authorized": False,
        },
    )

    return EquipmentTrustDecisionResult(
        evidence_id=str(evidence.pk),
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        unit_id=unit_id,
        decision=payload["decision"],
        evidence_digest=digest,
        trusted_equipment_decision_recorded=approve,
    )
