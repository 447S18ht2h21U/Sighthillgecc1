"""Development-only, read-only Installation Manager inspection workspace.
The five questions are the approved DocuSign inspection questions.
No answers, signatures, dates, evidence or provider operations are
accepted or created by this endpoint.
"""
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from core.models import Project, ProjectEvidence, Role, User
from core.installation_inspection_form_4945 import (
    INSPECTION_IDS, INSPECTION_ITEMS,
)
from core.post_installation_acceptance_4819 import INSPECTION_KIND, REVIEW_KIND, _check_inspection
from core.documents import canonical_hash

def internal_review_state(project, msr, schedule, approved, completed):
    """Inspect existing immutable candidates; never create or approve evidence."""
    if not approved or not completed:
        return "NOT_READY"

    inspections = list(ProjectEvidence.objects.filter(
        msr=msr, kind=INSPECTION_KIND
    ))
    reviews = list(ProjectEvidence.objects.filter(
        msr=msr, kind=REVIEW_KIND
    ))

    if not inspections and not reviews:
        return "NOT_RECORDED"
    if len(inspections) != 1 or len(reviews) > 1:
        return "EVIDENCE_REQUIRES_ATTENTION"

    inspection = inspections[0]
    try:
        data = _check_inspection(inspection, project, msr, schedule)
    except Exception:
        return "EVIDENCE_REQUIRES_ATTENTION"

    if (
        inspection.created_by_id != schedule.installation_manager_id
        or data.get("inspector_id") != str(schedule.installation_manager_id)
    ):
        return "EVIDENCE_REQUIRES_ATTENTION"

    if not reviews:
        return "AWAITING_INDEPENDENT_REVIEW"

    review = reviews[0]
    value = review.data
    if (
        type(value) is not dict
        or review.digest != canonical_hash(value)
        or review.msr_id != msr.pk
        or review.created_by_id == inspection.created_by_id
        or value.get("purpose") != REVIEW_KIND
        or value.get("inspection_id") != str(inspection.pk)
        or value.get("inspection_digest") != inspection.digest
        or value.get("project_id") != str(project.pk)
        or value.get("msr_id") != str(msr.pk)
        or value.get("msr_version") != msr.number
        or value.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or value.get("schedule_id") != str(schedule.pk)
        or value.get("inspector_id") != str(inspection.created_by_id)
        or value.get("reviewer_id") != str(review.created_by_id)
        or type(value.get("independently_examined")) is not bool
        or type(value.get("reason")) is not str
        or not 15 <= len(value["reason"].strip()) <= 2000
        or value.get("trusted_installation_evidence") is not False
        or value.get("final_receipt_issuance_authorized") is not False
        or not User.objects.filter(
            pk=review.created_by_id,
            is_active=True,
            role=Role.COMPTROLLER,
        ).exists()
    ):
        return "EVIDENCE_REQUIRES_ATTENTION"

    if value.get("status") == "CANDIDATE_ACCEPTED":
        if (
            data.get("inspection_passed") is not True
            or value["independently_examined"] is not True
        ):
            return "EVIDENCE_REQUIRES_ATTENTION"
        return "INTERNAL_CANDIDATE_ACCEPTED"
    if value.get("status") == "REJECTED":
        return "INTERNAL_CANDIDATE_REJECTED"
    return "EVIDENCE_REQUIRES_ATTENTION"


@api_view(["GET"])
def workspace(request, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Inspection workspace is not live-enabled.")
    actor = request.user
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    current = User.objects.filter(
        pk=actor.pk, is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()
    if current is None or actor.role != Role.INSTALLATION_MANAGER:
        raise PermissionDenied("Installation Manager access required.")
    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_id).first()
    if project is None or project.state == "CANCELLED":
        raise PermissionDenied("Active assigned project required.")
    from core.models import InstallationSchedule
    schedules = list(
        InstallationSchedule.objects.filter(
            project=project,
            installation_manager=current,
        ).order_by("pk")
    )
    # Never disclose another manager's project through this endpoint.
    if len(schedules) != 1:
        raise PermissionDenied("Assigned installation schedule required.")
    schedule = schedules[0]
    msr = project.current_approved
    approved = (
        msr is not None
        and msr.status == "APPROVED"
        and msr.project_id == project.pk
        and project.current_approved_id == msr.pk
        and type(msr.snapshot) is dict
    )
    from django.utils import timezone
    completed = (
        schedule.status == InstallationSchedule.Status.COMPLETED
        and schedule.completed_at is not None
        and schedule.cancelled_at is None
        and schedule.scheduled_date is not None
        and schedule.scheduled_date <= timezone.localdate()
        and schedule.completed_at <= timezone.now()
    )
    # A second completed schedule must never satisfy the identity gate.
    if completed and InstallationSchedule.objects.filter(
        project=project,
        status=InstallationSchedule.Status.COMPLETED,
    ).count() != 1:
        completed = False
    recorded = bool(
        approved and ProjectEvidence.objects.filter(
            msr=msr, kind=INSPECTION_KIND,
        ).exists()
    )
    state = (
        "APPROVED_MSR_REQUIRED" if not approved
        else "COMPLETED_INSTALLATION_REQUIRED" if not completed
        else "INSPECTION_ALREADY_RECORDED" if recorded
        else "READY_FOR_INSPECTION_REVIEW"
    )
    return Response({
        "project_id": str(project.pk),
        "state": state,
        "approved_msr": bool(approved),
        "completed_schedule": bool(completed),
        "inspection_already_recorded": recorded,
        "internal_review_state": internal_review_state(
            project, msr, schedule, approved, completed
        ),
        "questions": [
            {"id": key, "text": question}
            for key, question in zip(INSPECTION_IDS, INSPECTION_ITEMS)
        ],
        "answers_recorded_by_this_endpoint": False,
        "provider_signature_verified": False,
        "signed_date_verified": False,
        "receipt_issuance_authorized": False,
        "project_completion_authorized": False,
    })
