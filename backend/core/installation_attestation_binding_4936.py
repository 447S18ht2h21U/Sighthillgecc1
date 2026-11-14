"""Offline DocuSign Installation Inspection Attestation binding.

This service reads verified internal source evidence, but does not
authenticate the source, send envelopes, or authorize Receipt release.
"""

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_source_artifact_4826 import (
    SOURCE_KIND,
    _decode_artifact,
    verify_retained_installation_source,
)
from .models import Project, ProjectEvidence, Role, User
from .post_installation_acceptance_4819 import _completed_schedule


@dataclass(frozen=True)
class InstallationAttestationPreparation:
    project_id: str
    approved_msr_id: str
    approved_msr_version: int
    source_evidence_id: str
    source_pdf_sha256: str
    signer_user_id: str
    prepared_by_user_id: str
    binding_sha256: str
    status: str = "OFFLINE_ATTESTATION_BINDING_NOT_SENT"
    provider: str = "DOCUSIGN"
    provider_envelope_id: str | None = None
    provider_authenticated: bool = False
    source_artifact_authenticated: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def prepare_installation_attestation(*, actor, project_id, mode="OFFLINE_ONLY"):
    """Prepare a signer/source binding from persisted evidence only."""
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or mode != "OFFLINE_ONLY"
    ):
        raise PermissionDenied("Live attestation signing is disabled.")

    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated preparer required.")

    preparer = User.objects.filter(pk=actor.pk, is_active=True).first()
    if preparer is None or preparer.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        raise PermissionDenied("Authorized attestation preparer required.")

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_id).first()

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active persisted project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or type(msr.snapshot) is not dict
    ):
        raise ValidationError("Current approved MSR binding required.")

    schedule = _completed_schedule(project)
    if schedule is None:
        raise ValidationError("Completed installation schedule required.")

    signer = User.objects.filter(
        pk=schedule.installation_manager_id,
        is_active=True
    ).first()
    if signer is None or signer.role != Role.INSTALLATION_MANAGER:
        raise ValidationError("Assigned active Installation Manager required.")

    # A source PDF is only a candidate, even when its bytes are intact.
    if verify_retained_installation_source(project) is not True:
        raise ValidationError("Retained installation source integrity failed.")

    records = list(ProjectEvidence.objects.filter(
        msr=msr, kind=SOURCE_KIND
    ))
    if len(records) != 1:
        raise ValidationError("Exactly one retained source required.")

    record = records[0]
    data = record.data
    if (
        type(data) is not dict
        or record.msr_id != msr.pk
        or record.created_by_id != signer.pk
        or record.digest != canonical_hash(data)
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("schedule_id") != str(schedule.pk)
        or data.get("recorder_id") != str(signer.pk)
        or data.get("source_authenticated") is not False
        or data.get("trusted_installation_evidence") is not False
        or data.get("final_receipt_issuance_authorized") is not False
    ):
        raise ValidationError("Installation attestation source binding invalid.")

    # Independently decode and check the exact retained PDF bytes.
    try:
        content = _decode_artifact(data)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(
            "Retained installation source PDF integrity failed."
        ) from exc

    if not content.rstrip().endswith(b"%%EOF"):
        raise ValidationError("Complete installation source PDF required.")

    binding = {
        "purpose": "INSTALLATION_INSPECTION_ATTESTATION_4936",
        "project_id": str(project.pk),
        "approved_msr_id": str(msr.pk),
        "approved_msr_version": msr.number,
        "approved_snapshot_sha256": canonical_hash(msr.snapshot),
        "completed_schedule_id": str(schedule.pk),
        "inspection_id": data.get("inspection_id"),
        "inspection_digest": data.get("inspection_digest"),
        "source_evidence_id": str(record.pk),
        "source_pdf_sha256": data["content_sha256"],
        "signer_user_id": str(signer.pk),
        "prepared_by_user_id": str(preparer.pk),
        "provider": "DOCUSIGN",
    }
    if not all((
        binding["inspection_id"],
        binding["inspection_digest"],
        binding["source_pdf_sha256"],
    )):
        raise ValidationError("Inspection binding incomplete.")

    return InstallationAttestationPreparation(
        project_id=binding["project_id"],
        approved_msr_id=binding["approved_msr_id"],
        approved_msr_version=msr.number,
        source_evidence_id=binding["source_evidence_id"],
        source_pdf_sha256=binding["source_pdf_sha256"],
        signer_user_id=binding["signer_user_id"],
        prepared_by_user_id=binding["prepared_by_user_id"],
        binding_sha256=canonical_hash(binding),
    )
