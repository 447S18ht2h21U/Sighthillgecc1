"""Offline intake of purported DocuSign inspection evidence.

A caller-provided envelope status, PDF, certificate, or tab response
does NOT prove provider provenance. Genuine authenticated readback and
retained provider evidence must be integrated before approval.
"""

from dataclasses import dataclass
from hashlib import sha256
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_docusign_envelope_4962 import (
    OfflineInstallationEnvelope,
)
from .installation_docusign_response_4964 import (
    UnauthenticatedDocuSignObservation,
)


@dataclass(frozen=True)
class UnverifiedInspectionEvidenceBundle:
    project_id: str
    approved_msr_id: str
    approved_msr_version: str
    signer_user_id: str
    purported_envelope_id: str
    envelope_package_sha256: str
    response_observation_sha256: str
    signed_pdf_sha256: str
    certificate_sha256: str
    inspection_findings: tuple
    negative_inspection_ids: tuple
    bundle_sha256: str
    signed_pdf: bytes
    certificate_pdf: bytes
    status: str = "EVIDENCE_INTAKE_UNAUTHENTICATED"
    authenticated_provider_readback: bool = False
    envelope_binding_verified: bool = False
    signer_identity_verified: bool = False
    provider_signature_verified: bool = False
    provider_date_verified: bool = False
    provider_certificate_verified: bool = False
    stored_in_durable_evidence: bool = False
    corrective_actions_created: bool = False
    receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def _candidate_pdf(value, label):
    if (
        type(value) is not bytes
        or len(value) < 100
        or len(value) > 5_000_000
        or not value.startswith(b"%PDF-")
        or not value.rstrip().endswith(b"%%EOF")
    ):
        raise ValidationError(f"Invalid purported {label} PDF.")
    return sha256(value).hexdigest()


def assemble_unverified_inspection_evidence(
    *,
    envelope,
    observation,
    claimed_envelope_status,
    claimed_recipient_id,
    signed_pdf,
    certificate_pdf,
):
    """Bind untrusted provider-shaped inputs, without granting trust."""
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline evidence intake disabled.")

    if type(envelope) is not OfflineInstallationEnvelope:
        raise ValidationError("Offline source envelope required.")
    if type(observation) is not UnauthenticatedDocuSignObservation:
        raise ValidationError("Parsed response observation required.")

    if (
        envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.envelope_id is not None
        or envelope.provider_signed is not False
        or envelope.provider_validated is not False
        or envelope.completion_authorized is not False
        or observation.status != "PROVIDER_SHAPED_RESPONSE_UNAUTHENTICATED"
        or observation.live_provider_retrieval_verified is not False
        or observation.signer_identity_verified is not False
        or observation.completion_authorized is not False
    ):
        raise ValidationError("Source evidence asserts unauthorized trust.")

    if (
        observation.project_id != envelope.project_id
        or observation.approved_msr_id != envelope.approved_msr_id
        or observation.signer_user_id != envelope.signer_user_id
        or observation.envelope_package_sha256
        != envelope.envelope_package_sha256
    ):
        raise ValidationError("Project, signer or envelope binding mismatch.")

    if claimed_envelope_status != "completed":
        raise ValidationError("Purported completed envelope required.")

    if claimed_recipient_id != "1":
        raise ValidationError("Unexpected intended signer recipient.")

    if (
        type(observation.purported_envelope_id) is not str
        or not observation.purported_envelope_id.strip()
        or type(observation.observation_sha256) is not str
        or len(observation.observation_sha256) != 64
    ):
        raise ValidationError("Response identity malformed.")

    if (
        type(observation.selections) is not tuple
        or len(observation.selections) != 5
        or tuple(key for key, _ in observation.selections)
        != tuple(f"inspection_{i}" for i in range(1, 6))
        or any(answer not in ("YES", "NO")
               for _, answer in observation.selections)
    ):
        raise ValidationError("Incomplete five-question observation.")

    negatives = tuple(
        key for key, answer in observation.selections
        if answer == "NO"
    )
    if negatives != observation.negative_inspection_ids:
        raise ValidationError("Response classification mismatch.")

    signed_hash = _candidate_pdf(signed_pdf, "signed document")
    certificate_hash = _candidate_pdf(certificate_pdf, "certificate")

    if signed_hash == certificate_hash:
        raise ValidationError("Signed document and certificate identical.")
    if signed_hash == envelope.unsigned_pdf_sha256:
        raise ValidationError("Unsigned document cannot be signed evidence.")

    material = {
        "schema": "GECC_UNVERIFIED_IM_EVIDENCE_INTAKE_4966_V1",
        "project_id": envelope.project_id,
        "msr_id": envelope.approved_msr_id,
        "msr_version": envelope.approved_msr_version,
        "signer_user_id": envelope.signer_user_id,
        "purported_envelope_id": observation.purported_envelope_id,
        "envelope_package_sha256": envelope.envelope_package_sha256,
        "observation_sha256": observation.observation_sha256,
        "signed_pdf_sha256": signed_hash,
        "certificate_sha256": certificate_hash,
        "inspection_findings": observation.selections,
        "negative_inspection_ids": negatives,
    }
    digest = sha256(json.dumps(
        material, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()

    return UnverifiedInspectionEvidenceBundle(
        project_id=envelope.project_id,
        approved_msr_id=envelope.approved_msr_id,
        approved_msr_version=envelope.approved_msr_version,
        signer_user_id=envelope.signer_user_id,
        purported_envelope_id=observation.purported_envelope_id,
        envelope_package_sha256=envelope.envelope_package_sha256,
        response_observation_sha256=observation.observation_sha256,
        signed_pdf_sha256=signed_hash,
        certificate_sha256=certificate_hash,
        inspection_findings=observation.selections,
        negative_inspection_ids=negatives,
        bundle_sha256=digest,
        signed_pdf=bytes(signed_pdf),
        certificate_pdf=bytes(certificate_pdf),
    )
