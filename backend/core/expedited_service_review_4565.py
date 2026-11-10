"""Independent development-only expedited-service request review.

An accepted candidate does not grant a waiver, early installation,
trusted equipment status, or installation-start authority.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .expedited_service_request_4565 import KIND as REQUEST_KIND
from .models import Project, ProjectEvidence, Role, User
from .services import audit

REVIEW_KIND = "EXPEDITED_SERVICE_REVIEW"


@transaction.atomic
def review_expedited_service_request(
    *, actor, request_id, accept_candidate, review_reason
):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Expedited review is not live-enabled.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("An authenticated reviewer is required.")

    reviewer = User.objects.filter(pk=actor.pk).first()
    if (
        reviewer is None
        or reviewer.is_active is not True
        or reviewer.role != Role.COMPTROLLER
    ):
        raise PermissionDenied("Active Comptroller reviewer required.")

    if type(accept_candidate) is not bool:
        raise ValidationError("An explicit decision is required.")
    if type(review_reason) is not str or not 15 <= len(review_reason.strip()) <= 2000:
        raise ValidationError("A specific written review reason is required.")

    request = ProjectEvidence.objects.select_related("msr").filter(
        pk=request_id, kind=REQUEST_KIND
    ).first()
    if request is None:
        raise ValidationError("Valid expedited request required.")

    project = Project.objects.select_for_update().filter(
        pk=request.msr.project_id
    ).first()
    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.pk != request.msr_id
        or msr.project_id != project.pk
    ):
        raise ValidationError("Current approved MSR mismatch.")

    if request.created_by_id == reviewer.pk:
        raise PermissionDenied("Requester cannot review their own request.")

    data = request.data
    if type(data) is not dict or request.digest != canonical_hash(data):
        raise ValidationError("Request integrity failed.")

    if (
        data.get("status") != "PENDING_INDEPENDENT_VERIFICATION"
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or data.get("requested_by") != str(request.created_by_id)
        or type(data.get("proposed_date")) is not str
        or type(data.get("document_reference_claim")) is not str
        or not data["document_reference_claim"].strip()
        or any(data.get(key) is not False for key in (
            "customer_initials_verified",
            "document_signature_verified",
            "manager_approval_verified",
            "cancellation_protections_verified",
            "expedited_authorized",
            "installation_authorized",
        ))
    ):
        raise ValidationError("Request binding or safety flags invalid.")

    # Portable duplicate check; compatible with isolated SQLite.
    previous = ProjectEvidence.objects.filter(msr=msr, kind=REVIEW_KIND)
    if any(
        isinstance(record.data, dict)
        and record.data.get("request_id") == str(request.pk)
        for record in previous
    ):
        raise ValidationError("Request already reviewed.")

    payload = {
        "status": "CANDIDATE_ACCEPTED" if accept_candidate else "REJECTED",
        "request_id": str(request.pk),
        "request_digest": request.digest,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "proposed_date": data["proposed_date"],
        "document_reference_claim": data["document_reference_claim"],
        "requester_id": str(request.created_by_id),
        "reviewer_id": str(reviewer.pk),
        "review_reason": review_reason.strip(),
        "reviewed_at": timezone.now().isoformat(),
        "customer_initials_verified": False,
        "document_signature_verified": False,
        "manager_approval_verified": False,
        "cancellation_protections_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
    decision = ProjectEvidence.objects.create(
        msr=msr,
        kind=REVIEW_KIND,
        created_by=reviewer,
        data=payload,
        digest=canonical_hash(payload),
    )
    audit(reviewer, "installation.expedited_service_reviewed", project.pk, {
        "decision_id": str(decision.pk),
        "request_id": str(request.pk),
        "digest": decision.digest,
        "status": payload["status"],
        "installation_authorized": False,
    })
    return decision
