"""Independent read-back verification of an internal attestation preparation.

Stored preparation is never a DocuSign envelope, authenticated signature,
installation completion, FINAL Receipt, or project-completion approval.
"""

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError

from .documents import canonical_hash
from .installation_attestation_binding_4936 import (
    prepare_installation_attestation,
)
from .installation_attestation_record_4939 import KIND, PURPOSE
from .models import Project, ProjectEvidence, Role, User


@dataclass(frozen=True)
class AttestationRecordVerification:
    project_id: str
    msr_id: str
    evidence_id: str
    source_evidence_id: str
    binding_sha256: str
    record_integrity_verified: bool
    current_source_binding_verified: bool
    status: str = "PREPARATION_VERIFIED_NOT_SIGNED"
    provider_envelope_verified: bool = False
    source_artifact_authenticated: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def verify_attestation_preparation(*, project_id):
    """Recompute the preparation identity from independently read source data."""
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise ValidationError("Offline attestation verification is disabled.")

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
        raise ValidationError("Current approved MSR required.")

    records = list(ProjectEvidence.objects.filter(msr=msr, kind=KIND))
    if len(records) != 1:
        raise ValidationError("Exactly one preparation record required.")

    record = records[0]
    data = record.data
    if (
        type(data) is not dict
        or record.msr_id != msr.pk
        or record.digest != canonical_hash(data)
        or data.get("purpose") != PURPOSE
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("prepared_by_user_id") != str(record.created_by_id)
    ):
        raise ValidationError("Stored preparation identity or digest invalid.")

    preparer = User.objects.filter(
        pk=record.created_by_id, is_active=True
    ).first()
    if preparer is None or preparer.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        raise ValidationError("Authorized original preparer required.")

    prepared = prepare_installation_attestation(
        actor=preparer,
        project_id=project.pk,
        mode="OFFLINE_ONLY",
    )

    if (
        prepared.status != "OFFLINE_ATTESTATION_BINDING_NOT_SENT"
        or prepared.provider != "DOCUSIGN"
        or prepared.provider_envelope_id is not None
        or prepared.provider_authenticated is not False
        or prepared.source_artifact_authenticated is not False
        or prepared.trusted_installation_evidence is not False
        or prepared.final_receipt_issuance_authorized is not False
        or prepared.customer_delivery_verified is not False
        or prepared.completion_authorized is not False
    ):
        raise ValidationError("Preparation asserted unsupported authority.")

    expected = {
        "purpose": PURPOSE,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "source_evidence_id": prepared.source_evidence_id,
        "source_pdf_sha256": prepared.source_pdf_sha256,
        "binding_sha256": prepared.binding_sha256,
        "signer_user_id": prepared.signer_user_id,
        "prepared_by_user_id": str(preparer.pk),
        "provider": "DOCUSIGN",
        "status": "OFFLINE_ATTESTATION_BINDING_NOT_SENT",
        "envelope_created": False,
        "provider_authenticated": False,
        "source_artifact_authenticated": False,
        "trusted_installation_evidence": False,
        "final_receipt_issuance_authorized": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }

    if data != expected:
        raise ValidationError("Preparation differs from current source binding.")

    return AttestationRecordVerification(
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        evidence_id=str(record.pk),
        source_evidence_id=prepared.source_evidence_id,
        binding_sha256=prepared.binding_sha256,
        record_integrity_verified=True,
        current_source_binding_verified=True,
    )
