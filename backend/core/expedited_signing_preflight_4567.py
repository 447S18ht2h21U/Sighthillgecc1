"""Read-only, development-only MSR-bound expedited signing preflight.

Uses existing immutable request, independent review and manager decision.
Never sends a document, records customer consent, or authorizes installation.
"""
from datetime import date
from uuid import UUID

from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import Project, ProjectEvidence, Role, User
from .expedited_chain_readiness_4566 import assess_expedited_chain
from .expedited_service_request_4565 import KIND as REQUEST_KIND
from .expedited_service_review_4565 import REVIEW_KIND
from .expedited_manager_decision_4565 import DECISION_KIND


ALLOWED_ROLES = frozenset((
    Role.CEO, Role.COMPTROLLER, Role.INSTALLATION_MANAGER,
    Role.SALES_MANAGER,
))
REQUIRED_KINDS = (REQUEST_KIND, REVIEW_KIND, DECISION_KIND)


def assess_unified_signing_preflight(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Unified signing is not live-enabled.")

    actor_id = getattr(actor, "pk", None)
    user = User.objects.filter(pk=actor_id).first() if actor_id else None
    if (
        user is None or user.is_active is not True
        or user.role not in ALLOWED_ROLES
    ):
        raise PermissionDenied("Active authorized GECC reviewer required.")

    try:
        project_uuid = UUID(str(project_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Valid project identifier required.") from None

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_uuid).first()

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved
    if (
        msr is None or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    assessment = assess_expedited_chain(project)
    if (
        type(assessment) is not dict
        or assessment.get("expedited_chain_reviewed") is not True
    ):
        raise ValidationError("Expedited administrative chain incomplete.")

    rows = list(
        ProjectEvidence.objects.filter(
            msr=msr, kind__in=REQUIRED_KINDS,
        )
    )
    if (
        len(rows) != 3
        or {item.kind for item in rows} != set(REQUIRED_KINDS)
    ):
        raise ValidationError("Exactly one record of each evidence kind required.")

    records = {item.kind: item for item in rows}
    request = records[REQUEST_KIND]
    review = records[REVIEW_KIND]
    decision = records[DECISION_KIND]
    snapshot_hash = canonical_hash(msr.snapshot)

    for record in rows:
        data = record.data
        if (
            record.msr_id != msr.pk
            or type(data) is not dict
            or record.digest != canonical_hash(data)
            or data.get("project_id") != str(project.pk)
            or data.get("msr_id") != str(msr.pk)
            or data.get("snapshot_sha256") != snapshot_hash
            or data.get("msr_version") != msr.number
        ):
            raise ValidationError("MSR evidence integrity or version mismatch.")

    proposed_date = request.data.get("proposed_date")
    try:
        normalized_date = date.fromisoformat(proposed_date).isoformat()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid proposed installation date.") from None

    if (
        proposed_date != normalized_date
        or review.data.get("proposed_date") != normalized_date
        or decision.data.get("proposed_date") != normalized_date
        or review.data.get("request_id") != str(request.pk)
        or review.data.get("request_digest") != request.digest
        or decision.data.get("request_id") != str(request.pk)
        or decision.data.get("request_digest") != request.digest
        or decision.data.get("review_id") != str(review.pk)
        or decision.data.get("review_digest") != review.digest
        or request.data.get("requested_by") != str(request.created_by_id)
        or review.data.get("reviewer_id") != str(review.created_by_id)
        or request.data.get("status") != "PENDING_INDEPENDENT_VERIFICATION"
        or review.data.get("status") != "CANDIDATE_ACCEPTED"
        or decision.data.get("status")
            != "MANAGER_APPROVED_PENDING_CUSTOMER_EVIDENCE"
    ):
        raise ValidationError("Expedited evidence chain does not agree.")

    if len({
        request.created_by_id,
        review.created_by_id,
        decision.created_by_id,
    }) != 3:
        raise ValidationError("Three distinct administrative actors required.")

    return {
        "status": "MSR_BOUND_ADMINISTRATIVE_PREFLIGHT_ONLY",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": snapshot_hash,
        "proposed_date": normalized_date,
        "document_kinds": ["CUSTOMER_SOW", "EXPEDITED_SERVICE"],
        "envelope_count": 1,
        "administrative_records": {
            "request_id": str(request.pk),
            "request_digest": request.digest,
            "review_id": str(review.pk),
            "review_digest": review.digest,
            "manager_decision_id": str(decision.pk),
            "manager_decision_digest": decision.digest,
        },
        "administrative_chain_reviewed": True,
        "customer_signer_authorized": False,
        "source_document_verified": False,
        "provider_identity_verified": False,
        "customer_signatures_verified": False,
        "reviewer_signatures_verified": False,
        "signed_documents_retained": False,
        "distribution_verified": False,
        "legal_eligibility_verified": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
