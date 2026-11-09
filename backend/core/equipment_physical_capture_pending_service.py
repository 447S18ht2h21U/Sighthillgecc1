"""Unregistered development-only physical inspection evidence foundation.

Captures an immutable inspection CLAIM, not independently trusted proof.
Never grants equipment exception or installation-start authority.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_trusted_evidence_preparation import (
    prepare_physical_equipment_evidence,
)
from .models import Project, ProjectEvidence, Role, User
from .services import audit


KIND = "PHYSICAL_UNIT_CAPTURE_PENDING"


@transaction.atomic
def record_pending_physical_inspection(
    *, actor, project_id, msr_id, unit_id, serial_number,
    captured_at, installation_starts_at,
    confirmed_in_person, inspection_notes,
):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Inspection prototype is development-only.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated Installation Manager required.")

    recorder = User.objects.filter(pk=actor.pk).first()
    if (
        recorder is None
        or recorder.is_active is not True
        or recorder.role != Role.INSTALLATION_MANAGER
    ):
        raise PermissionDenied("Active Installation Manager required.")

    if confirmed_in_person is not True:
        raise ValidationError("Explicit physical inspection attestation required.")

    if (
        type(inspection_notes) is not str
        or not 15 <= len(inspection_notes.strip()) <= 2000
    ):
        raise ValidationError("Specific written inspection notes required.")

    project = Project.objects.select_for_update().filter(
        pk=project_id
    ).first()
    if project is None:
        raise ValidationError("Project does not exist.")

    # The existing preparation chain checks the current approved MSR,
    # per-unit mapping, recorder identity, serial and capture time.
    candidate = prepare_physical_equipment_evidence(
        project_id=project.pk,
        msr_id=msr_id,
        unit_id=unit_id,
        serial_number=serial_number,
        recorder_id=str(recorder.pk),
        captured_at=captured_at,
        installation_starts_at=installation_starts_at,
    )
    if candidate.preparation_complete is not True:
        raise ValidationError(list(candidate.blockers))

    msr = project.current_approved
    if (
        msr is None
        or str(msr.pk) != candidate.msr_id
        or msr.status != "APPROVED"
        or project.state == "CANCELLED"
    ):
        raise ValidationError("Current approved MSR required.")

    existing = ProjectEvidence.objects.filter(
        msr=msr, kind=KIND
    )
    for record in existing:
        data = record.data
        if type(data) is not dict:
            raise ValidationError("Existing inspection evidence is invalid.")
        if (
            data.get("unit_id") == unit_id
            or data.get("serial_number") == candidate.normalized_serial
        ):
            raise ValidationError("Duplicate unit or serial inspection.")

    payload = {
        "purpose": "PHYSICAL_INSPECTION_PENDING_VERIFICATION",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "unit_id": candidate.unit_id,
        "serial_number": candidate.normalized_serial,
        "recorded_by": str(recorder.pk),
        "captured_at": captured_at.isoformat(),
        "recorded_at": timezone.now().isoformat(),
        "confirmed_in_person": True,
        "inspection_notes": inspection_notes.strip(),
        "independently_verified": False,
        "trusted_installation_evidence": False,
        "installation_authorized": False,
    }

    digest = canonical_hash(payload)
    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=KIND,
        created_by=recorder,
        data=payload,
        digest=digest,
    )

    audit(
        recorder,
        "equipment.physical_inspection_pending",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "msr_id": str(msr.pk),
            "unit_id": candidate.unit_id,
            "digest": digest,
            "trusted_installation_evidence": False,
        },
    )

    return evidence