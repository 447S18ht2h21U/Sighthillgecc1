"""Unregistered development-only physical-unit serial capture.

Records immutable, audited, synthetic identification evidence.
Never grants installation, exception, release, or delivery authority.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .models import Project, ProjectEvidence, Role, User
from .services import audit


SERIAL_KIND = "EQUIPMENT_SERIAL_CAPTURE"


@transaction.atomic
def capture_synthetic_serial(
    *, actor, project_id, msr_id, unit_id, serial_number
):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError("Synthetic serial capture is development-only.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("An authenticated Installation Manager is required.")

    recorder = User.objects.get(pk=actor.pk)
    if not recorder.is_active or recorder.role != Role.INSTALLATION_MANAGER:
        raise PermissionDenied(
            "Only an active Installation Manager may capture a serial."
        )

    if type(unit_id) is not str or not unit_id.strip():
        raise ValidationError("A specific physical unit is required.")

    if type(serial_number) is not str:
        raise ValidationError("A serial number must be text.")

    serial = serial_number.strip().upper()
    if (
        not serial
        or len(serial) > 120
        or any(ord(c) < 32 or ord(c) == 127 for c in serial)
    ):
        raise ValidationError("A valid physical-unit serial number is required.")

    project = Project.objects.select_for_update().get(pk=project_id)
    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or str(msr.pk) != str(msr_id)
    ):
        raise ValidationError(
            "Serial evidence requires this project's current approved MSR."
        )

    try:
        units = physical_units_from_snapshot(
            msr_id=str(msr.pk), snapshot=msr.snapshot
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if unit_id not in {unit.unit_id for unit in units}:
        raise ValidationError("Physical unit is not in the approved MSR.")

    for existing in ProjectEvidence.objects.filter(
        msr=msr, kind=SERIAL_KIND
    ):
        if existing.data.get("unit_id") == unit_id:
            raise ValidationError(
                "This physical unit already has a serial capture record."
            )
        if (
            type(existing.data.get("serial_number")) is str
            and existing.data["serial_number"].strip().upper() == serial
        ):
            raise ValidationError(
                "A serial number cannot identify two physical units."
            )

    payload = {
        "purpose": "SYNTHETIC_SERIAL_CAPTURE",
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "unit_id": unit_id,
        "serial_number": serial,
        "recorded_by": str(recorder.pk),
        "recorded_at": timezone.now().isoformat(),
        "trusted_installation_evidence": False,
        "installation_authorized": False,
    }

    digest = canonical_hash(payload)
    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=SERIAL_KIND,
        created_by=recorder,
        data=payload,
        digest=digest,
    )

    audit(
        recorder,
        "equipment.serial_captured_synthetic",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "msr_id": str(msr.pk),
            "unit_id": unit_id,
            "digest": digest,
            "trusted_installation_evidence": False,
        },
    )
    return evidence