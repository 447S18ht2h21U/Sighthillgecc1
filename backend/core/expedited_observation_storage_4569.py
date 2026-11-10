
'''Development-only retention of UNVERIFIED expedited signing evidence.

Neither a recorded PDF nor an envelope identity proves DocuSign origin.
This service grants no sending, approval, or installation authority.
'''
from hashlib import sha256
from io import BytesIO
from uuid import UUID

from django.conf import settings
from django.db import transaction
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import (
    Role, ExpeditedEnvelopeBinding, ExpeditedSigningObservation,
    ExpeditedSigningDocument, ProjectEvidence,
)

ROLES = (Role.CEO, Role.SALES_MANAGER)
DOCUMENTS = {
    "1": "Expedited SOW candidate.pdf",
    "2": "Expedited Service Request candidate.pdf",
    "certificate": "DocuSign certificate candidate.pdf",
}
MAX_BYTES = 20 * 1024 * 1024


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical UUID required.")
    try:
        normalized = str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Invalid UUID.") from None
    if normalized != value:
        raise ValidationError("Noncanonical UUID.")
    return normalized


@transaction.atomic
def retain_unverified_expedited_observation(
    *, actor, binding_id, candidate, pdf_bytes,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Expedited retention is not live-enabled.")

    if (
        actor is None
        or getattr(actor, "role", None) not in ROLES
        or getattr(actor, "is_active", False) is not True
        or not getattr(actor, "pk", None)
    ):
        raise PermissionDenied("Authorized manager required.")

    binding_id = _uuid(binding_id)
    binding = (
        ExpeditedEnvelopeBinding.objects.select_for_update()
        .select_related("attempt__msr__project")
        .get(pk=binding_id)
    )
    attempt = binding.attempt
    msr = attempt.msr
    if (
        attempt.initiated_by_id != actor.pk
        or binding.bound_by_id != actor.pk
        or msr.status != "APPROVED"
        or msr.project.current_approved_id != msr.pk
        or canonical_hash(msr.snapshot) != attempt.snapshot_sha256
    ):
        raise ValidationError("MSR-bound envelope integrity differs.")

    evidence_rows = list(ProjectEvidence.objects.filter(
        msr=msr,
        kind="EXPEDITED_ENVELOPE_BINDING",
        data__binding_id=binding_id,
    ))
    if len(evidence_rows) != 1:
        raise ValidationError("Binding audit evidence missing.")

    prior = evidence_rows[0]
    data = prior.data
    if (
        prior.created_by_id != binding.bound_by_id
        or prior.digest != canonical_hash(data)
        or data.get("attempt_id") != str(attempt.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("provider_account_id") != str(binding.provider_account_id)
        or data.get("provider_envelope_id") != str(binding.provider_envelope_id)
        or data.get("source_digest") != attempt.source_digest
        or data.get("state") != "SANDBOX_IDENTITY_CLAIM_UNVERIFIED"
        or data.get("provider_authenticated") is not False
        or data.get("installation_authorized") is not False
    ):
        raise ValidationError("Recorded envelope binding is inconsistent.")

    if type(candidate) is not dict or (
        candidate.get("status") != "SANDBOX_READ_STRUCTURAL_CANDIDATE_ONLY"
        or candidate.get("envelope_id")
            != str(binding.provider_envelope_id)
        or candidate.get("source_msr_id") != str(msr.pk)
        or candidate.get("provider_origin_bound_to_msr") is not False
        or candidate.get("provider_authenticated") is not False
        or candidate.get("installation_authorized") is not False
        or candidate.get("send_authorized") is not False
    ):
        raise ValidationError("Only untrusted structural observations allowed.")

    expected = candidate.get("document_hashes")
    if (
        type(expected) is not dict or set(expected) != set(DOCUMENTS)
        or type(pdf_bytes) is not dict or set(pdf_bytes) != set(DOCUMENTS)
    ):
        raise ValidationError("Two documents and certificate required.")

    rows = []
    for doc_id, filename in DOCUMENTS.items():
        content = pdf_bytes[doc_id]
        if (
            type(content) is not bytes
            or not 8 <= len(content) <= MAX_BYTES
            or not content.startswith(b"%PDF-")
            or type(expected[doc_id]) is not str
            or len(expected[doc_id]) != 64
        ):
            raise ValidationError("Invalid PDF evidence candidate.")

        actual = sha256(content).hexdigest()
        if actual != expected[doc_id]:
            raise ValidationError("Document fingerprint differs.")

        try:
            pdf = PdfReader(BytesIO(content), strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 150:
                raise ValueError("Invalid PDF")
        except Exception:
            raise ValidationError("PDF structure invalid.") from None

        rows.append({
            "document_id": doc_id,
            "filename": filename,
            "content": content,
            "pdf_sha256": actual,
        })

    if ExpeditedSigningObservation.objects.filter(binding=binding).exists():
        raise ValidationError("Observation already retained.")

    metadata = {
        "binding_id": binding_id,
        "attempt_id": str(attempt.pk),
        "msr_id": str(msr.pk),
        "envelope_id": str(binding.provider_envelope_id),
        "source_digest": attempt.source_digest,
        "document_hashes": {
            item["document_id"]: item["pdf_sha256"] for item in rows
        },
        "status": "UNVERIFIED_DOCUMENT_BYTES_RETAINED",
        "provider_authenticated": False,
        "signed_documents_verified": False,
        "distribution_verified": False,
        "installation_authorized": False,
    }
    observation = ExpeditedSigningObservation.objects.create(
        binding=binding,
        observed_by=actor,
        evidence=metadata,
        digest=canonical_hash(metadata),
    )
    for row in rows:
        ExpeditedSigningDocument.objects.create(
            observation=observation, **row
        )

    project_evidence = {
        **metadata,
        "observation_id": str(observation.pk),
        "document_count": 3,
    }
    ProjectEvidence.objects.create(
        msr=msr,
        kind="EXPEDITED_DOCUMENT_RETENTION",
        created_by=actor,
        data=project_evidence,
        digest=canonical_hash(project_evidence),
    )

    return {
        "status": "UNVERIFIED_DOCUMENT_BYTES_RETAINED",
        "observation_id": str(observation.pk),
        "binding_id": binding_id,
        "msr_id": str(msr.pk),
        "document_hashes": metadata["document_hashes"],
        "provider_authenticated": False,
        "signed_documents_verified": False,
        "distribution_verified": False,
        "installation_authorized": False,
        "send_authorized": False,
    }
