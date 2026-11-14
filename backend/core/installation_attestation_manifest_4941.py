"""Offline installation-specific DocuSign document binding manifest.

The source PDF is a supporting attachment, NOT a signed attestation.
A separate signable attestation PDF and verified DocuSign envelope
will be required before installation source authenticity can be asserted.
"""

from dataclasses import dataclass
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_attestation_record_4939 import KIND
from .installation_attestation_verifier_4940 import (
    verify_attestation_preparation,
)
from .installation_source_artifact_4826 import (
    SOURCE_KIND,
    _decode_artifact,
)
from .models import Project, ProjectEvidence, Role, User


@dataclass(frozen=True)
class InstallationSigningManifest:
    project_id: str
    approved_msr_id: str
    approved_msr_version: int
    preparation_evidence_id: str
    source_evidence_id: str
    source_pdf_sha256: str
    source_pdf: bytes
    signer_user_id: str
    signer_email: str
    signer_name: str
    attestation_binding_sha256: str
    manifest_sha256: str
    status: str = "OFFLINE_MANIFEST_NOT_SENT"
    source_document_role: str = "SUPPORTING_SOURCE_NOT_SIGNED"
    attestation_pdf_created: bool = False
    envelope_created: bool = False
    signer_authenticated: bool = False
    source_artifact_authenticated: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def build_installation_signing_manifest(*, actor, project_id):
    """Read exact retained source bytes; do not create or send an envelope."""
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline installation signing is disabled.")

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
        raise ValidationError("Current approved MSR required.")

    verified = verify_attestation_preparation(project_id=project.pk)
    if (
        verified.project_id != str(project.pk)
        or verified.msr_id != str(msr.pk)
        or verified.record_integrity_verified is not True
        or verified.current_source_binding_verified is not True
        or verified.provider_envelope_verified is not False
        or verified.source_artifact_authenticated is not False
        or verified.trusted_installation_evidence is not False
        or verified.final_receipt_issuance_authorized is not False
        or verified.customer_delivery_verified is not False
        or verified.completion_authorized is not False
    ):
        raise ValidationError("Independent attestation preparation failed.")

    preparations = list(
        ProjectEvidence.objects.filter(msr=msr, kind=KIND)
    )
    sources = list(
        ProjectEvidence.objects.filter(msr=msr, kind=SOURCE_KIND)
    )
    if len(preparations) != 1 or len(sources) != 1:
        raise ValidationError("Unique attestation and source evidence required.")

    preparation, source = preparations[0], sources[0]
    data, original = preparation.data, source.data

    if (
        type(data) is not dict
        or type(original) is not dict
        or preparation.msr_id != msr.pk
        or source.msr_id != msr.pk
        or preparation.digest != canonical_hash(data)
        or source.digest != canonical_hash(original)
        or str(preparation.pk) != verified.evidence_id
        or str(source.pk) != verified.source_evidence_id
        or data.get("source_evidence_id") != str(source.pk)
        or data.get("source_pdf_sha256") != verified_source_digest(original)
        or data.get("binding_sha256") != verified.binding_sha256
        or data.get("prepared_by_user_id") != str(preparer.pk)
        or preparation.created_by_id != preparer.pk
        or data.get("provider") != "DOCUSIGN"
        or data.get("status") != "OFFLINE_ATTESTATION_BINDING_NOT_SENT"
        or data.get("envelope_created") is not False
        or data.get("provider_authenticated") is not False
        or data.get("source_artifact_authenticated") is not False
        or data.get("trusted_installation_evidence") is not False
        or data.get("final_receipt_issuance_authorized") is not False
        or data.get("customer_delivery_verified") is not False
        or data.get("completion_authorized") is not False
    ):
        raise ValidationError("Source and preparation binding mismatch.")

    signer = User.objects.filter(
        pk=data.get("signer_user_id"), is_active=True
    ).first()
    if (
        signer is None
        or signer.role != Role.INSTALLATION_MANAGER
        or str(signer.pk) != str(source.created_by_id)
        or str(signer.pk) != original.get("recorder_id")
    ):
        raise ValidationError("Assigned Installation Manager mismatch.")

    email = getattr(signer, "email", None)
    if not isinstance(email, str) or email != email.strip():
        raise ValidationError("Valid Installation Manager email required.")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValidationError(
            "Valid Installation Manager email required."
        ) from exc

    name = signer.get_full_name().strip()
    if not name:
        raise ValidationError("Installation Manager full name required.")

    try:
        pdf = _decode_artifact(original)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Retained installation PDF invalid.") from exc

    if (
        not pdf.rstrip().endswith(b"%%EOF")
        or sha256(pdf).hexdigest() != data["source_pdf_sha256"]
    ):
        raise ValidationError("Exact retained installation PDF mismatch.")

    identity = {
        "purpose": "DOCUSIGN_INSTALLATION_SIGNING_MANIFEST_4941",
        "project_id": str(project.pk),
        "approved_msr_id": str(msr.pk),
        "approved_msr_version": msr.number,
        "preparation_evidence_id": str(preparation.pk),
        "source_evidence_id": str(source.pk),
        "source_pdf_sha256": sha256(pdf).hexdigest(),
        "signer_user_id": str(signer.pk),
        "signer_email": email,
        "signer_name": name,
        "attestation_binding_sha256": verified.binding_sha256,
        "source_document_role": "SUPPORTING_SOURCE_NOT_SIGNED",
    }

    return InstallationSigningManifest(
        project_id=str(project.pk),
        approved_msr_id=str(msr.pk),
        approved_msr_version=msr.number,
        preparation_evidence_id=str(preparation.pk),
        source_evidence_id=str(source.pk),
        source_pdf_sha256=identity["source_pdf_sha256"],
        source_pdf=pdf,
        signer_user_id=str(signer.pk),
        signer_email=email,
        signer_name=name,
        attestation_binding_sha256=verified.binding_sha256,
        manifest_sha256=canonical_hash(identity),
    )


def verified_source_digest(data):
    value = data.get("content_sha256")
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValidationError("Retained source digest format invalid.")
    return value
