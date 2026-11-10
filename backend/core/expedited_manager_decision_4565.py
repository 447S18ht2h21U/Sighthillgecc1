"""Audited, development-only Installation Manager decision.

Neither a favorable decision nor a reviewed request authorizes early
installation, waives cancellation rights, or verifies customer initials.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .expedited_service_request_4565 import KIND as REQUEST_KIND
from .expedited_service_review_4565 import REVIEW_KIND
from .models import Project, ProjectEvidence, Role, User
from .services import audit

DECISION_KIND = "EXPEDITED_MANAGER_DECISION"


@transaction.atomic
def decide_expedited_service_request(
    *, actor, review_id, approve, decision_reason
):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Manager decisions are not live-enabled.")

    manager_id = getattr(actor, "pk", None)
    manager = User.objects.filter(pk=manager_id).first() if manager_id else None
    if not manager or not manager.is_active or manager.role != Role.INSTALLATION_MANAGER:
        raise PermissionDenied("Active Installation Manager required.")

    if type(approve) is not bool:
        raise ValidationError("Explicit approval or rejection required.")
    if type(decision_reason) is not str or not 15 <= len(decision_reason.strip()) <= 2000:
        raise ValidationError("Specific written decision reason required.")

    review = ProjectEvidence.objects.select_related("msr").filter(
        pk=review_id, kind=REVIEW_KIND
    ).first()
    if review is None:
        raise ValidationError("Independent review record required.")

    project = Project.objects.select_for_update().filter(
        pk=review.msr.project_id
    ).first()
    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved
    if (
        msr is None or msr.status != "APPROVED"
        or msr.pk != review.msr_id or msr.project_id != project.pk
    ):
        raise ValidationError("Current approved MSR required.")

    data = review.data
    if type(data) is not dict or review.digest != canonical_hash(data):
        raise ValidationError("Independent review integrity failed.")

    safety_keys = (
        "customer_initials_verified",
        "document_signature_verified",
        "manager_approval_verified",
        "cancellation_protections_verified",
        "expedited_authorized",
        "installation_authorized",
    )
    if (
        data.get("status") not in ("CANDIDATE_ACCEPTED", "REJECTED")
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or data.get("reviewer_id") != str(review.created_by_id)
        or any(data.get(key) is not False for key in safety_keys)
    ):
        raise ValidationError("Review binding or safety flags invalid.")

    request = ProjectEvidence.objects.filter(
        pk=data.get("request_id"), msr=msr, kind=REQUEST_KIND
    ).first()
    if (
        request is None
        or request.digest != canonical_hash(request.data)
        or data.get("request_digest") != request.digest
        or request.created_by_id == review.created_by_id
        or request.data.get("requested_by") != str(request.created_by_id)
        or request.data.get("proposed_date") != data.get("proposed_date")
        or request.data.get("msr_id") != str(msr.pk)
        or request.data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or request.data.get("status") != "PENDING_INDEPENDENT_VERIFICATION"
        or any(request.data.get(key) is not False for key in safety_keys)
    ):
        raise ValidationError("Original request binding invalid.")

    if approve and data["status"] != "CANDIDATE_ACCEPTED":
        raise ValidationError("Rejected review cannot receive approval.")

    if any(
        isinstance(item.data, dict)
        and item.data.get("review_id") == str(review.pk)
        for item in ProjectEvidence.objects.filter(msr=msr, kind=DECISION_KIND)
    ):
        raise ValidationError("Manager decision already recorded.")

    payload = {
        "status": (
            "MANAGER_APPROVED_PENDING_CUSTOMER_EVIDENCE"
            if approve else "MANAGER_REJECTED"
        ),
        "review_id": str(review.pk),
        "review_digest": review.digest,
        "request_id": str(request.pk),
        "request_digest": request.digest,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "proposed_date": data["proposed_date"],
        "manager_id": str(manager.pk),
        "decision_reason": decision_reason.strip(),
        "decided_at": timezone.now().isoformat(),
        "manager_decision_recorded": approve,
        "customer_initials_verified": False,
        "document_signature_verified": False,
        "cancellation_protections_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
    decision = ProjectEvidence.objects.create(
        msr=msr, kind=DECISION_KIND, created_by=manager,
        data=payload, digest=canonical_hash(payload),
    )
    audit(manager, "installation.expedited_manager_decided", project.pk, {
        "decision_id": str(decision.pk),
        "review_id": str(review.pk),
        "digest": decision.digest,
        "status": payload["status"],
        "expedited_authorized": False,
        "installation_authorized": False,
    })
    return decision
