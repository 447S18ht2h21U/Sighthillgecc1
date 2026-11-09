"""Unregistered, fail-closed Invoice delivery binding preflight.

All expected values must be supplied by an independent trusted record
reader, never by the delivery claimant. This pure function does NOT
verify that such a reader is trusted, or establish actual delivery.
"""
from dataclasses import dataclass
from hmac import compare_digest
from uuid import UUID


@dataclass(frozen=True)
class InvoiceBindingResult:
    candidate_matches: bool
    trusted_delivery: bool = False
    installation_evidence_accepted: bool = False


def _id(value):
    if not isinstance(value, str):
        raise ValueError("Expected a UUID string.")
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid UUID.") from exc


def verify_candidate_binding(
    candidate,
    *,
    current_approved_msr_id,
    expected_document_id,
    expected_pdf_sha256,
    expected_recipient_email,
    expected_document_kind,
    document_status,
    document_msr_id,
):
    """Reject stale or mismatched candidates; never authorize installation."""
    if type(candidate.trusted_delivery) is not bool or candidate.trusted_delivery:
        raise ValueError("Untrusted candidate is required.")
    if (type(candidate.installation_evidence_accepted) is not bool
            or candidate.installation_evidence_accepted):
        raise ValueError("Already-authorized evidence is not accepted.")

    ids_match = (
        _id(candidate.msr_id) == _id(current_approved_msr_id)
        == _id(document_msr_id)
        and _id(candidate.document_id) == _id(expected_document_id)
    )

    if not isinstance(expected_pdf_sha256, str) or len(expected_pdf_sha256) != 64:
        raise ValueError("Expected PDF fingerprint is invalid.")
    if not isinstance(candidate.invoice_sha256, str) or len(candidate.invoice_sha256) != 64:
        raise ValueError("Candidate PDF fingerprint is invalid.")

    hash_matches = compare_digest(
        candidate.invoice_sha256.lower(), expected_pdf_sha256.lower()
    )
    recipient_matches = (
        isinstance(expected_recipient_email, str)
        and bool(expected_recipient_email.strip())
        and candidate.recipient_email.casefold()
        == expected_recipient_email.casefold()
    )

    # PREPARATION documents are not evidence of delivered invoices.
    # Other statuses cannot be trusted until independently defined.
    matches = (
        ids_match
        and hash_matches
        and recipient_matches
        and expected_document_kind == "INVOICE"
        and document_status == "PREPARATION"
    )
    return InvoiceBindingResult(candidate_matches=bool(matches))