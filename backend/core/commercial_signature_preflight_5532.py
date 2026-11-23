"""Read-only commercial DocuSign evidence correlation.

This is NOT independent signature authentication. It performs strict
cross-record checks and never authorizes installation or completion.

No provider requests, persistence, or side effects occur here.
"""

import hashlib
from datetime import datetime, timezone
from uuid import UUID


def _uuid(value):
    try:
        if not isinstance(value, str):
            return None
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _timestamp(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def assess_commercial_evidence(
    *,
    expected_msr_id,
    expected_kind,
    expected_customer_email,
    account_id,
    envelope_id,
    provider_summary,
    provider_signers,
    expected_release_binding=None,
    signed_pdf,
    certificate_pdf,
    retained_signed_sha256,
    retained_certificate_sha256,
):
    """Correlate provider-shaped evidence without granting trust.

    Callers must not treat a successful assessment as authenticated proof.
    Provider data and documents must still be independently retrieved
    through a controlled OAuth readback and signature verifier.
    """
    blockers = []

    if expected_kind not in {"CONTRACT", "INVOICE"}:
        blockers.append("Unsupported commercial document type.")

    if _uuid(expected_msr_id) is None:
        blockers.append("Approved MSR identity is invalid.")

    account = _uuid(account_id)
    envelope = _uuid(envelope_id)

    if account is None or envelope is None:
        blockers.append("DocuSign account or envelope identity is invalid.")

    if not isinstance(expected_release_binding, dict):
        blockers.append("Trusted release-to-MSR binding is missing.")
    else:
        if (
            _uuid(expected_release_binding.get("msr_id"))
            != _uuid(expected_msr_id)
            or _uuid(expected_msr_id) is None
        ):
            blockers.append("Release binding does not match the approved MSR.")

        if expected_release_binding.get("document_kind") != expected_kind:
            blockers.append("Release binding document type does not match.")

        if (
            _uuid(expected_release_binding.get("envelope_id"))
            != envelope
            or envelope is None
        ):
            blockers.append("Release binding envelope does not match.")

        if (
            _uuid(expected_release_binding.get("account_id"))
            != account
            or account is None
        ):
            blockers.append("Release binding account does not match.")

    if not isinstance(provider_summary, dict):
        blockers.append("Provider envelope summary is missing.")
        provider_summary = {}

    if (
        envelope is None
        or _uuid(provider_summary.get("envelopeId")) != envelope
        or provider_summary.get("status") != "completed"
    ):
        blockers.append("Completed provider envelope does not match.")

    if not isinstance(expected_customer_email, str):
        expected_customer_email = ""

    email = expected_customer_email.strip().casefold()
    if not email or "@" not in email:
        blockers.append("Expected customer email is missing.")

    if not isinstance(provider_signers, list):
        provider_signers = []

    matching = [
        signer for signer in provider_signers
        if isinstance(signer, dict)
        and isinstance(signer.get("email"), str)
        and signer["email"].strip().casefold() == email
        and signer.get("status") == "completed"
    ]

    if not email or len(matching) != 1:
        blockers.append(
            "Exactly one completed matching customer signer is required."
        )

    if len(provider_signers) != len([
        signer.get("recipientId")
        for signer in provider_signers
        if isinstance(signer, dict)
        and isinstance(signer.get("recipientId"), str)
        and signer.get("recipientId")
    ]):
        blockers.append("Provider signer identities are incomplete.")

    signer_ids = [
        signer.get("recipientId")
        for signer in provider_signers
        if isinstance(signer, dict)
    ]
    if len(signer_ids) != len(set(signer_ids)):
        blockers.append("Duplicate provider signer identity detected.")

    signed_at = None
    if len(matching) == 1:
        signed_at = _timestamp(matching[0].get("signed_at"))
        if signed_at is None:
            blockers.append("Customer signing timestamp is unverified.")

    completed_at = _timestamp(provider_summary.get("completed_at"))
    if completed_at is None:
        blockers.append("Envelope completion timestamp is unverified.")

    if signed_at and completed_at and signed_at > completed_at:
        blockers.append("Signing occurred after envelope completion.")

    now = datetime.now(timezone.utc)
    if completed_at and completed_at > now:
        blockers.append("Envelope completion timestamp is in the future.")

    if signed_at and signed_at > now:
        blockers.append("Customer signing timestamp is in the future.")

    documents = [
        ("Signed document", signed_pdf, retained_signed_sha256),
        ("Certificate", certificate_pdf, retained_certificate_sha256),
    ]

    for label, payload, digest in documents:
        if (
            not isinstance(payload, bytes)
            or not payload.startswith(b"%PDF-")
            or not isinstance(digest, str)
            or len(digest) != 64
            or hashlib.sha256(payload).hexdigest() != digest.lower()
        ):
            blockers.append(f"{label} bytes or retained digest do not match.")

    if expected_kind == "CONTRACT":
        document_label = "Customer Contract"
    elif expected_kind == "INVOICE":
        document_label = "Customer Invoice"
    else:
        document_label = "Unsupported document"

    return {
        "document": document_label,
        "correlation_passed": not blockers,
        "signature_authenticated": False,
        "installation_authorized": False,
        "completion_authorized": False,
        "blockers": blockers,
        "authentication_requirement": (
            "Independent provider signer, document, and certificate "
            "authentication is still required."
        ),
    }
