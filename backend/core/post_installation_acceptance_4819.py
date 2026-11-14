"""Development-only post-installation inspection and independent review.

Records are immutable candidates, not provider-authenticated evidence.
No FINAL Receipt issuance, delivery or project completion authority.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import (
    InstallationSchedule, Project, ProjectEvidence, Role, User,
)
from .services import audit

INSPECTION_KIND = "POST_INSTALL_INSPECT_4819"
REVIEW_KIND = "POST_INSTALL_REVIEW_4819"


def _development_only():
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Evidence recording is not live-enabled.")


def _actor(actor, required_role):
    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated reviewer required.")
    user = User.objects.filter(pk=actor.pk).first()
    if (
        user is None
        or user.is_active is not True
        or user.role != required_role
    ):
        raise PermissionDenied("Authorized active role required.")
    return user


def _current_project(project_id):
    project = Project.objects.select_for_update().select_related(
        "current_approved"
    ).filter(pk=project_id).first()
    if project is None:
        raise ValidationError("Existing project required.")

    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or type(msr.snapshot) is not dict
    ):
        raise ValidationError("Current approved MSR required.")
    return project, msr


def _completed_schedule(project):
    schedules = list(InstallationSchedule.objects.filter(
        project=project,
        status=InstallationSchedule.Status.COMPLETED,
    ).order_by("pk"))

    if len(schedules) != 1:
        raise ValidationError("Exactly one completed schedule required.")

    schedule = schedules[0]
    if (
        schedule.completed_at is None
        or schedule.cancelled_at is not None
        or schedule.scheduled_date is None
        or schedule.scheduled_date > timezone.localdate()
        or schedule.completed_at > timezone.now()
    ):
        raise ValidationError("Installation completion is inconsistent.")

    return schedule


def _check_inspection(record, project, msr, schedule):
    data = record.data
    if type(data) is not dict or record.digest != canonical_hash(data):
        raise ValidationError("Inspection evidence integrity failed.")

    if (
        record.msr_id != msr.pk
        or record.kind != INSPECTION_KIND
        or data.get("purpose") != INSPECTION_KIND
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or data.get("schedule_id") != str(schedule.pk)
        or data.get("schedule_completed_at") != schedule.completed_at.isoformat()
        or data.get("inspector_id") != str(record.created_by_id)
        or type(data.get("inspection_passed")) is not bool
        or type(data.get("notes")) is not str
        or not 15 <= len(data["notes"].strip()) <= 2000
        or data.get("independently_verified") is not False
        or data.get("trusted_installation_evidence") is not False
        or data.get("final_receipt_issuance_authorized") is not False
    ):
        raise ValidationError("Inspection binding or outcome is invalid.")
    return data


@transaction.atomic
def record_post_installation_inspection(
    *, actor, project_id, inspection_passed, notes
):
    _development_only()
    inspector = _actor(actor, Role.INSTALLATION_MANAGER)

    if type(inspection_passed) is not bool:
        raise ValidationError("Explicit inspection outcome required.")
    if type(notes) is not str or not 15 <= len(notes.strip()) <= 2000:
        raise ValidationError("Specific inspection notes required.")

    project, msr = _current_project(project_id)
    schedule = _completed_schedule(project)

    if schedule.installation_manager_id != inspector.pk:
        raise PermissionDenied("Assigned Installation Manager required.")

    if ProjectEvidence.objects.filter(
        msr=msr, kind=INSPECTION_KIND
    ).exists():
        raise ValidationError("Inspection already recorded for this MSR.")

    payload = {
        "purpose": INSPECTION_KIND,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "schedule_id": str(schedule.pk),
        "schedule_completed_at": schedule.completed_at.isoformat(),
        "inspector_id": str(inspector.pk),
        "inspection_passed": inspection_passed,
        "notes": notes.strip(),
        "recorded_at": timezone.now().isoformat(),
        "independently_verified": False,
        "trusted_installation_evidence": False,
        "final_receipt_issuance_authorized": False,
    }

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=INSPECTION_KIND,
        created_by=inspector,
        data=payload,
        digest=canonical_hash(payload),
    )
    audit(inspector, "installation.post_inspection_recorded", project.pk, {
        "evidence_id": str(record.pk),
        "digest": record.digest,
        "passed": inspection_passed,
        "receipt_authorized": False,
    })
    return record


@transaction.atomic
def review_post_installation_inspection(
    *, actor, inspection_id, accept, reason, independently_examined
):
    _development_only()
    reviewer = _actor(actor, Role.COMPTROLLER)

    if type(accept) is not bool or type(independently_examined) is not bool:
        raise ValidationError("Explicit review decision required.")
    if accept and independently_examined is not True:
        raise ValidationError("Acceptance requires independent examination.")
    if type(reason) is not str or not 15 <= len(reason.strip()) <= 2000:
        raise ValidationError("Written review reason required.")

    inspection = ProjectEvidence.objects.filter(
        pk=inspection_id, kind=INSPECTION_KIND
    ).first()
    if inspection is None:
        raise ValidationError("Valid inspection evidence required.")

    project, msr = _current_project(inspection.msr.project_id)
    schedule = _completed_schedule(project)
    data = _check_inspection(inspection, project, msr, schedule)

    if inspection.created_by_id == reviewer.pk:
        raise PermissionDenied("Self-review prohibited.")
    if accept and data["inspection_passed"] is not True:
        raise ValidationError("Failed installation inspection cannot be accepted.")

    if ProjectEvidence.objects.filter(
        msr=msr, kind=REVIEW_KIND
    ).exists():
        raise ValidationError("Independent review already recorded.")

    payload = {
        "purpose": REVIEW_KIND,
        "status": "CANDIDATE_ACCEPTED" if accept else "REJECTED",
        "inspection_id": str(inspection.pk),
        "inspection_digest": inspection.digest,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "schedule_id": str(schedule.pk),
        "inspector_id": str(inspection.created_by_id),
        "reviewer_id": str(reviewer.pk),
        "independently_examined": independently_examined,
        "reason": reason.strip(),
        "reviewed_at": timezone.now().isoformat(),
        "trusted_installation_evidence": False,
        "final_receipt_issuance_authorized": False,
    }

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=REVIEW_KIND,
        created_by=reviewer,
        data=payload,
        digest=canonical_hash(payload),
    )
    audit(reviewer, "installation.post_inspection_reviewed", project.pk, {
        "review_id": str(record.pk),
        "inspection_id": str(inspection.pk),
        "status": payload["status"],
        "digest": record.digest,
        "receipt_authorized": False,
    })
    return record
