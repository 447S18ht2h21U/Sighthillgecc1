"""Read-only verification of retained post-installation evidence.

Internal candidate verification is not external authentication, physical
installation certification, Receipt issuance, delivery, or completion.
"""
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from .documents import canonical_hash
from .models import (
    InstallationSchedule, ProjectEvidence, Role, User,
)
from .post_installation_acceptance_4819 import (
    INSPECTION_KIND, REVIEW_KIND,
)


@dataclass(frozen=True)
class PostInstallationAcceptanceVerification:
    project_id: str
    msr_id: str
    inspection_count: int
    review_count: int
    acceptance_candidate_verified: bool
    blockers: tuple[str, ...]
    post_installation_acceptance_verified: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def verify_post_installation_acceptance(project):
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    pid = str(project.pk)
    msr = getattr(project, "current_approved", None)
    mid = str(msr.pk) if msr is not None else ""

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or project.state == "CANCELLED"
        or type(msr.snapshot) is not dict
    ):
        raise ValueError("Active approved MSR required.")

    inspections = list(ProjectEvidence.objects.filter(
        msr=msr, kind=INSPECTION_KIND
    ))
    reviews = list(ProjectEvidence.objects.filter(
        msr=msr, kind=REVIEW_KIND
    ))

    def denied(message):
        return PostInstallationAcceptanceVerification(
            project_id=pid,
            msr_id=mid,
            inspection_count=len(inspections),
            review_count=len(reviews),
            acceptance_candidate_verified=False,
            blockers=(message,),
        )

    if len(inspections) != 1 or len(reviews) != 1:
        return denied("Exactly one inspection and independent review required.")

    schedules = list(InstallationSchedule.objects.filter(
        project=project,
        status=InstallationSchedule.Status.COMPLETED,
    ))
    if len(schedules) != 1:
        return denied("Exactly one completed installation schedule required.")

    schedule = schedules[0]
    now = timezone.now()
    if (
        schedule.completed_at is None
        or schedule.cancelled_at is not None
        or schedule.scheduled_date is None
        or schedule.scheduled_date > timezone.localdate()
        or schedule.completed_at > now
    ):
        return denied("Completed installation schedule is inconsistent.")

    inspection = inspections[0]
    review = reviews[0]
    p, r = inspection.data, review.data

    if (
        type(p) is not dict
        or type(r) is not dict
        or inspection.digest != canonical_hash(p)
        or review.digest != canonical_hash(r)
    ):
        return denied("Retained evidence digest verification failed.")

    inspector = User.objects.filter(pk=inspection.created_by_id).first()
    reviewer = User.objects.filter(pk=review.created_by_id).first()
    if (
        inspector is None
        or reviewer is None
        or inspector.is_active is not True
        or reviewer.is_active is not True
        or inspector.role != Role.INSTALLATION_MANAGER
        or reviewer.role != Role.COMPTROLLER
        or inspector.pk == reviewer.pk
        or schedule.installation_manager_id != inspector.pk
    ):
        return denied("Inspection or review authority verification failed.")

    snapshot_hash = canonical_hash(msr.snapshot)
    if (
        p.get("purpose") != INSPECTION_KIND
        or p.get("project_id") != pid
        or p.get("msr_id") != mid
        or p.get("msr_version") != msr.number
        or p.get("snapshot_sha256") != snapshot_hash
        or p.get("schedule_id") != str(schedule.pk)
        or p.get("schedule_completed_at")
            != schedule.completed_at.isoformat()
        or p.get("inspector_id") != str(inspector.pk)
        or p.get("inspection_passed") is not True
        or type(p.get("notes")) is not str
        or not 15 <= len(p["notes"].strip()) <= 2000
        or p.get("independently_verified") is not False
        or p.get("trusted_installation_evidence") is not False
        or p.get("final_receipt_issuance_authorized") is not False
    ):
        return denied("Post-installation inspection binding invalid.")

    if (
        r.get("purpose") != REVIEW_KIND
        or r.get("status") != "CANDIDATE_ACCEPTED"
        or r.get("inspection_id") != str(inspection.pk)
        or r.get("inspection_digest") != inspection.digest
        or r.get("project_id") != pid
        or r.get("msr_id") != mid
        or r.get("msr_version") != msr.number
        or r.get("snapshot_sha256") != snapshot_hash
        or r.get("schedule_id") != str(schedule.pk)
        or r.get("inspector_id") != str(inspector.pk)
        or r.get("reviewer_id") != str(reviewer.pk)
        or r.get("independently_examined") is not True
        or type(r.get("reason")) is not str
        or not 15 <= len(r["reason"].strip()) <= 2000
        or r.get("trusted_installation_evidence") is not False
        or r.get("final_receipt_issuance_authorized") is not False
    ):
        return denied("Independent acceptance review binding invalid.")

    try:
        captured_at = datetime.fromisoformat(p["recorded_at"])
        reviewed_at = datetime.fromisoformat(r["reviewed_at"])
        inspection_stored_at = getattr(inspection, "created_at", None)
        review_stored_at = getattr(review, "created_at", None)
        if (
            not isinstance(inspection_stored_at, datetime)
            or not isinstance(review_stored_at, datetime)
            or timezone.is_naive(captured_at)
            or timezone.is_naive(reviewed_at)
            or timezone.is_naive(inspection_stored_at)
            or timezone.is_naive(review_stored_at)
            or not (
                schedule.completed_at
                <= captured_at
                <= inspection_stored_at
                <= reviewed_at
                <= review_stored_at
                <= now
            )
        ):
            raise ValueError("Invalid persisted evidence chronology.")
    except (ValueError, TypeError, KeyError, OverflowError):
        return denied("Inspection and review chronology invalid.")

    return PostInstallationAcceptanceVerification(
        project_id=pid,
        msr_id=mid,
        inspection_count=1,
        review_count=1,
        acceptance_candidate_verified=True,
        blockers=(
            "Internal acceptance candidate does not establish "
            "independently authenticated installation completion.",
        ),
    )
