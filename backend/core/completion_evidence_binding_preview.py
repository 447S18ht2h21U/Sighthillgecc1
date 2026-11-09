"""Strict candidate bindings for future Receipt and DocuSign evidence.

This module validates identifiers and relationships only. Data supplied
to it is not independently authenticated. Operational completion
authorization is always false. No network, database writes or routes.
"""
from dataclasses import dataclass
import hashlib
import re
from uuid import UUID


_SHA = re.compile(r"[0-9a-f]{64}", re.ASCII)


@dataclass(frozen=True)
class EvidenceBindingPreview:
    receipt_candidate_bound: bool
    certificate_candidate_bound: bool
    candidate_evidence_complete: bool
    blockers: tuple[str, ...]
    evidence_trusted: bool = False
    project_completion_authorized: bool = False
    project_completed: bool = False


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _digest(value):
    if not isinstance(value, str):
        return None
    normalized = value.lower()
    return normalized if _SHA.fullmatch(normalized) else None


def _pdf(content, fingerprint):
    if not isinstance(content, bytes) or not content.startswith(b"%PDF-"):
        return False
    digest = _digest(fingerprint)
    return digest is not None and hashlib.sha256(content).hexdigest() == digest


def assess_completion_evidence_bindings(
    *,
    project_id,
    msr_id,
    customer_email,
    receipt,
    email_evidence,
    certificate,
    provider_evidence,
    satisfaction_survey_received=False,
):
    """Evaluate candidate record relationships; never assert trust."""
    project_key = _uuid(project_id)
    msr_key = _uuid(msr_id)
    reasons = []

    if not project_key or not msr_key:
        reasons.append("Valid project and approved MSR identifiers required.")

    if (
        not isinstance(customer_email, str)
        or not customer_email.strip()
        or "@" not in customer_email
    ):
        reasons.append("Customer email identity is missing.")

    if type(satisfaction_survey_received) is not bool:
        raise ValueError("Survey status must be boolean.")

    def field(record, name):
        return record.get(name) if type(record) is dict else None

    def common(record):
        return (
            project_key is not None
            and msr_key is not None
            and _uuid(field(record, "project_id")) == project_key
            and _uuid(field(record, "msr_id")) == msr_key
        )

    receipt_id = _uuid(field(receipt, "document_id"))
    receipt_sha = _digest(field(receipt, "pdf_sha256"))
    receipt_ok = (
        common(receipt)
        and receipt_id is not None
        and receipt_sha is not None
        and field(receipt, "kind") in ("RECEIPT", "INVOICE")
        and _pdf(field(receipt, "pdf"), receipt_sha)
    )

    if not receipt_ok:
        reasons.append("Retained final Receipt binding or PDF fingerprint is invalid.")

    recipient = field(email_evidence, "recipient_email")
    message_id = field(email_evidence, "provider_message_id")
    email_ok = (
        receipt_ok
        and common(email_evidence)
        and _uuid(field(email_evidence, "document_id")) == receipt_id
        and _digest(field(email_evidence, "pdf_sha256")) == receipt_sha
        and isinstance(recipient, str)
        and isinstance(customer_email, str)
        and recipient.strip().casefold() == customer_email.strip().casefold()
        and isinstance(message_id, str)
        and bool(message_id.strip())
        and field(email_evidence, "provider_status") == "SENT"
    )

    if not email_ok:
        reasons.append(
            "Receipt email candidate must match the exact PDF, customer "
            "email and provider sending reference."
        )

    certificate_id = _uuid(field(certificate, "document_id"))
    certificate_sha = _digest(field(certificate, "pdf_sha256"))
    kind = field(certificate, "kind")
    certificate_ok = (
        common(certificate)
        and certificate_id is not None
        and kind in ("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED")
        and _pdf(field(certificate, "pdf"), certificate_sha)
    )

    envelope = field(provider_evidence, "envelope_id")
    provider_ok = (
        certificate_ok
        and common(provider_evidence)
        and _uuid(field(provider_evidence, "document_id")) == certificate_id
        and _digest(field(provider_evidence, "pdf_sha256")) == certificate_sha
        and field(provider_evidence, "certificate_kind") == kind
        and _uuid(envelope) is not None
        and field(provider_evidence, "status") == "completed"
        and isinstance(field(provider_evidence, "provider_account_id"), str)
        and bool(field(provider_evidence, "provider_account_id").strip())
    )
    if not provider_ok:
        reasons.append(
            "Completed DocuSign candidate must match the retained "
            "certificate, project, MSR, envelope and provider status."
        )

    reasons.append(
        "Candidate records are not authenticated provider evidence. "
        "Independent verification and operational authorization are required."
    )

    return EvidenceBindingPreview(
        receipt_candidate_bound=bool(receipt_ok and email_ok),
        certificate_candidate_bound=bool(provider_ok),
        candidate_evidence_complete=bool(receipt_ok and email_ok and provider_ok),
        blockers=tuple(reasons),
    )