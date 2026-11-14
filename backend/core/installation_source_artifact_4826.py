"""Development-only retained installation source artifact.

Exact PDF bytes are retained in immutable ProjectEvidence JSON.
This bounded implementation is not a production document-storage design.
Source integrity does NOT establish source authenticity or installation trust.
"""
from base64 import b64encode, b64decode
from binascii import Error as Base64Error
from hashlib import sha256

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from .documents import canonical_hash
from .models import ProjectEvidence, Role
from .post_installation_acceptance_4819 import (
    INSPECTION_KIND, _actor, _current_project,
    _completed_schedule, _check_inspection, _development_only,
)
from .services import audit

SOURCE_KIND = "POST_INSTALL_SOURCE_4826"
MAX_BYTES = 1024 * 1024


def _decode_artifact(data):
    encoded = data.get("content_base64")
    if (
        type(encoded) is not str
        or len(encoded) > ((MAX_BYTES + 2) // 3) * 4
    ):
        raise ValueError("Source artifact encoding invalid.")

    try:
        content = b64decode(encoded, validate=True)
    except (ValueError, Base64Error):
        raise ValueError("Source artifact encoding invalid.") from None

    if (
        len(content) < 8
        or len(content) > MAX_BYTES
        or not content.startswith(b"%PDF-")
        or data.get("size_bytes") != len(content)
        or data.get("content_sha256") != sha256(content).hexdigest()
    ):
        raise ValueError("Source artifact fingerprint invalid.")

    return content


def verify_retained_installation_source(project):
    """Revalidate persisted identity, chronology, digest, and exact bytes."""
    msr = getattr(project, "current_approved", None)
    if (
        project is None
        or getattr(project, "pk", None) is None
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or project.state == "CANCELLED"
        or type(msr.snapshot) is not dict
    ):
        raise ValueError("Active approved project required.")

    records = list(ProjectEvidence.objects.filter(
        msr=msr, kind=SOURCE_KIND
    ))
    if len(records) != 1:
        return False

    record = records[0]
    data = record.data
    if type(data) is not dict:
        return False

    try:
        schedule = _completed_schedule(project)
        inspections = list(ProjectEvidence.objects.filter(
            msr=msr, kind=INSPECTION_KIND
        ))
        if len(inspections) != 1:
            return False

        inspection = inspections[0]
        inspected = _check_inspection(
            inspection, project, msr, schedule
        )

        if (
            record.digest != canonical_hash(data)
            or record.msr_id != msr.pk
            or record.created_by_id != inspection.created_by_id
            or data.get("purpose") != SOURCE_KIND
            or data.get("project_id") != str(project.pk)
            or data.get("msr_id") != str(msr.pk)
            or data.get("msr_version") != msr.number
            or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
            or data.get("schedule_id") != str(schedule.pk)
            or data.get("inspection_id") != str(inspection.pk)
            or data.get("inspection_digest") != inspection.digest
            or data.get("recorder_id") != str(record.created_by_id)
            or data.get("media_type") != "application/pdf"
            or data.get("source_authenticated") is not False
            or data.get("trusted_installation_evidence") is not False
            or data.get("final_receipt_issuance_authorized") is not False
            or inspected.get("inspection_passed") is not True
        ):
            return False

        recorder = _actor_id(record.created_by_id)
        if (
            recorder is None
            or recorder.role != Role.INSTALLATION_MANAGER
            or schedule.installation_manager_id != recorder.pk
            or record.created_at < inspection.created_at
            or record.created_at > timezone.now()
        ):
            return False

        _decode_artifact(data)
        return True
    except (ValueError, TypeError, AttributeError, ValidationError):
        return False


def _actor_id(pk):
    from .models import User
    return User.objects.filter(pk=pk, is_active=True).first()


@transaction.atomic
def retain_installation_source(
    *, actor, project_id, inspection_id, content, description
):
    """Capture one immutable PDF with audit; no authority is granted."""
    _development_only()
    recorder = _actor(actor, Role.INSTALLATION_MANAGER)

    if type(content) is not bytes:
        raise ValidationError("Exact PDF bytes required.")
    if (
        len(content) < 8
        or len(content) > MAX_BYTES
        or not content.startswith(b"%PDF-")
    ):
        raise ValidationError("Bounded PDF artifact required.")
    if type(description) is not str or not 15 <= len(description.strip()) <= 500:
        raise ValidationError("Specific source description required.")

    project, msr = _current_project(project_id)
    schedule = _completed_schedule(project)
    if schedule.installation_manager_id != recorder.pk:
        raise PermissionDenied("Assigned Installation Manager required.")

    inspection = ProjectEvidence.objects.filter(
        pk=inspection_id, msr=msr, kind=INSPECTION_KIND
    ).first()
    if inspection is None:
        raise ValidationError("Existing inspection required.")

    inspected = _check_inspection(
        inspection, project, msr, schedule
    )
    if (
        inspected["inspection_passed"] is not True
        or inspection.created_by_id != recorder.pk
    ):
        raise ValidationError("Passing inspection by recorder required.")

    if ProjectEvidence.objects.filter(
        msr=msr, kind=SOURCE_KIND
    ).exists():
        raise ValidationError("Source artifact already retained.")

    payload = {
        "purpose": SOURCE_KIND,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "schedule_id": str(schedule.pk),
        "inspection_id": str(inspection.pk),
        "inspection_digest": inspection.digest,
        "recorder_id": str(recorder.pk),
        "description": description.strip(),
        "media_type": "application/pdf",
        "size_bytes": len(content),
        "content_sha256": sha256(content).hexdigest(),
        "content_base64": b64encode(content).decode("ascii"),
        "source_authenticated": False,
        "trusted_installation_evidence": False,
        "final_receipt_issuance_authorized": False,
    }

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=SOURCE_KIND,
        created_by=recorder,
        data=payload,
        digest=canonical_hash(payload),
    )

    audit(
        recorder,
        "installation.source_artifact_retained",
        project.pk,
        {
            "evidence_id": str(record.pk),
            "inspection_id": str(inspection.pk),
            "content_sha256": payload["content_sha256"],
            "source_authenticated": False,
            "receipt_authorized": False,
        },
    )
    return record
