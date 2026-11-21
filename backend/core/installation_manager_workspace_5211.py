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
from core.post_installation_acceptance_4819 import INSPECTION_KIND
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
