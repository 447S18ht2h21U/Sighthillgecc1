
'''Offline reconciliation of three DocuSign document byte streams.

Structural metadata and PDF integrity are NOT authenticated DocuSign
provenance, durable retention, or customer distribution.
'''
from hashlib import sha256
from io import BytesIO
from uuid import UUID

from django.conf import settings
from pypdf import PdfReader
from rest_framework.exceptions import PermissionDenied, ValidationError

from .expedited_three_signer_evidence_4568 import (
    validate_three_signer_observation,
)

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
REQUIRED_IDS = frozenset(("1", "2", "certificate"))


def validate_retention_candidate(
    *, expected_envelope_id, offline_envelope,
    summary, recipients, documents, signed_pdfs,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Expedited retention is not live-enabled.")

    # Reuse the existing three-signer chronology and decision checks.
    signed = validate_three_signer_observation(
        expected_envelope_id=expected_envelope_id,
        offline_envelope=offline_envelope,
        summary=summary,
        recipients=recipients,
    )
    if (
        type(signed) is not dict
        or signed.get("status") != "THREE_SIGNER_STRUCTURAL_CANDIDATE_ONLY"
        or signed.get("envelope_id") != expected_envelope_id
        or signed.get("provider_authenticated") is not False
        or signed.get("installation_authorized") is not False
    ):
        raise ValidationError("Protected three-signer assessment invalid.")

    try:
        envelope_id = str(UUID(expected_envelope_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid envelope identifier.") from None

    if envelope_id != expected_envelope_id:
        raise ValidationError("Canonical envelope identifier required.")

    source_docs = offline_envelope.get("documents")
    if type(source_docs) is not list or len(source_docs) != 2:
        raise ValidationError("Two approved source documents required.")

    expected_names = {}
    for index, item in enumerate(source_docs, start=1):
        if (
            type(item) is not dict
            or item.get("documentId") != str(index)
            or type(item.get("name")) is not str
            or not item["name"]
        ):
            raise ValidationError("Original document identity differs.")
        expected_names[str(index)] = item["name"]

    if type(documents) is not dict:
        raise ValidationError("Provider document metadata missing.")

    observed = documents.get("envelopeDocuments")
    if type(observed) is not list or len(observed) != 3:
        raise ValidationError("Two PDFs and a certificate entry required.")

    observed_ids = []
    for item in observed:
        if type(item) is not dict:
            raise ValidationError("Invalid document metadata entry.")
        doc_id = str(item.get("documentId", ""))
        name = item.get("name")
        if (
            doc_id not in REQUIRED_IDS
            or type(name) is not str
            or not name.strip()
        ):
            raise ValidationError("Unexpected signed-document identity.")
        if doc_id in expected_names and name != expected_names[doc_id]:
            raise ValidationError("Signed document name differs from source.")
        observed_ids.append(doc_id)

    if len(set(observed_ids)) != 3 or set(observed_ids) != REQUIRED_IDS:
        raise ValidationError("Missing or duplicate signed document identity.")

    if type(signed_pdfs) is not dict or set(signed_pdfs) != REQUIRED_IDS:
        raise ValidationError("Exactly three retrieved PDFs required.")

    hashes = {}
    for doc_id in ("1", "2", "certificate"):
        data = signed_pdfs[doc_id]
        if (
            type(data) is not bytes
            or not 8 <= len(data) <= MAX_DOCUMENT_BYTES
            or not data.startswith(b"%PDF-")
        ):
            raise ValidationError("Missing or invalid signed PDF bytes.")
        try:
            pdf = PdfReader(BytesIO(data), strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 150:
                raise ValueError("Invalid PDF structure")
        except Exception:
            raise ValidationError("Signed PDF structure failed.") from None

        hashes[doc_id] = sha256(data).hexdigest()

    # These hashes identify retrieved bytes. They do not prove that
    # the bytes came from DocuSign or were durably stored.
    return {
        "status": "THREE_DOCUMENT_STRUCTURAL_CANDIDATE_ONLY",
        "envelope_id": envelope_id,
        "source_msr_id": offline_envelope.get("source_msr_id"),
        "manager_candidate_decision":
            signed["manager_candidate_decision"],
        "comptroller_candidate_decision":
            signed["comptroller_candidate_decision"],
        "retrieved_document_hashes": hashes,
        "provider_authenticated": False,
        "signed_documents_verified": False,
        "certificate_verified": False,
        "durably_retained": False,
        "distribution_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
