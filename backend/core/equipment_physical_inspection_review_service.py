"""Unregistered independent review of pending physical inspection claims.

Prototype: active Comptroller only, never the recorder.
Records an immutable review decision but NO trusted installation evidence,
equipment exception effectiveness, or installation-start authorization.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_physical_capture_pending_service import KIND as PENDING_KIND
from .equipment_physical_units import physical_units_from_snapshot
from .models import Project, ProjectEvidence, Role, User
from .services import audit

REVIEW_KIND = "PHYSICAL_INSPECTION_REVIEW"


@transaction.atomic
def review_pending_physical_inspection(
    *, actor, pending_id, accept_candidate, review_reason,
    independently_examined,
):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Review prototype is development-only.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated independent reviewer required.")

    reviewer = User.objects.filter(pk=actor.pk).first()
    if (
        reviewer is None
        or reviewer.is_active is not True
        or reviewer.role != Role.COMPTROLLER
    ):
        raise PermissionDenied("Active Comptroller reviewer required.")

    if type(accept_candidate) is not bool:
        raise ValidationError("An explicit review decision is required.")
    if type(review_reason) is not str or not 15 <= len(review_reason.strip()) <= 2000:
        raise ValidationError("A specific written review reason is required.")
    if type(independently_examined) is not bool:
        raise ValidationError("Explicit independent examination status required.")
    if accept_candidate and independently_examined is not True:
        raise ValidationError("A favorable review requires independent examination.")

    pending = ProjectEvidence.objects.select_related("msr").filter(
        pk=pending_id
    ).first()
    if pending is None or pending.kind != PENDING_KIND:
        raise ValidationError("Valid pending inspection evidence required.")

    project = Project.objects.select_for_update().filter(
        pk=pending.msr.project_id
    ).first()
    if project is None:
        raise ValidationError("Project does not exist.")

    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.pk != pending.msr_id
        or msr.project_id != project.pk
    ):
        raise ValidationError("Current approved MSR does not match.")

    data = pending.data
    if type(data) is not dict or pending.digest != canonical_hash(data):
        raise ValidationError("Pending evidence integrity failed.")

    if (
        data.get("purpose") != "PHYSICAL_INSPECTION_PENDING_VERIFICATION"
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or data.get("recorded_by") != str(pending.created_by_id)
        or data.get("confirmed_in_person") is not True
        or data.get("independently_verified") is not False
        or data.get("trusted_installation_evidence") is not False
        or data.get("installation_authorized") is not False
        or type(data.get("serial_number")) is not str
        or not data["serial_number"].strip()
    ):
        raise ValidationError("Pending inspection binding is invalid.")

    if pending.created_by_id == reviewer.pk:
        raise PermissionDenied("Recorder cannot review their own inspection.")

    try:
        expected_units = physical_units_from_snapshot(
            msr_id=str(msr.pk), snapshot=msr.snapshot
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError("Approved equipment snapshot is invalid.") from exc

    if data.get("unit_id") not in {unit.unit_id for unit in expected_units}:
        raise ValidationError("Inspection references an unknown physical unit.")

    for existing in ProjectEvidence.objects.filter(
        msr=msr, kind=REVIEW_KIND
    ):
        if type(existing.data) is not dict:
            raise ValidationError("Review history is malformed.")
        if existing.data.get("pending_id") == str(pending.pk):
            raise ValidationError("This inspection already has a review decision.")

    payload = {
        "status": "CANDIDATE_ACCEPTED" if accept_candidate else "REJECTED",
        "pending_id": str(pending.pk),
        "pending_digest": pending.digest,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "unit_id": data["unit_id"],
        "recorder_id": str(pending.created_by_id),
        "reviewer_id": str(reviewer.pk),
        "review_reason": review_reason.strip(),
        "independently_examined": independently_examined,
        "reviewed_at": timezone.now().isoformat(),
        "trusted_installation_evidence": False,
        "installation_authorized": False,
    }

    digest = canonical_hash(payload)
    decision = ProjectEvidence.objects.create(
        msr=msr,
        kind=REVIEW_KIND,
        created_by=reviewer,
        data=payload,
        digest=digest,
    )

    audit(
        reviewer,
        "equipment.physical_inspection_reviewed",
        project.pk,
        {
            "decision_id": str(decision.pk),
            "pending_id": str(pending.pk),
            "status": payload["status"],
            "digest": digest,
            "trusted_installation_evidence": False,
        },
    )
    return decision