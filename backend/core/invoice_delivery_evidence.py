"""Unregistered Invoice delivery evidence preflight.

Pure validation only. No database reads/writes, document delivery, provider
calls, installation authorization, or trusted-delivery assertions.

Passing this preflight NEVER proves delivery. Source authenticity, trusted
receipt verification, role authority, audit, persistence and revocation
must be checked independently by a future approved service.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import UUID


_HEX_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_CHANNELS = frozenset({"PROVIDER_EMAIL", "VERIFIED_PORTAL"})


@dataclass(frozen=True)
class DeliveryEvidenceCandidate:
    msr_id: str
    document_id: str
    invoice_sha256: str
    recipient_email: str
    channel: str
    provider_reference: str
    delivered_at: datetime
    verified_by_id: str
    verified_at: datetime
    trusted_delivery: bool = False
    installation_evidence_accepted: bool = False


def _uuid(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a UUID string.")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"{name} must be a valid UUID.") from exc
    return str(parsed)


def _aware(value, name, now):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be a timezone-aware datetime.")
    try:
        utc = value.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} has an invalid timezone.") from exc
    if utc > now:
        raise ValueError(f"{name} cannot be in the future.")
    return utc


def assess_delivery_candidate(
    *,
    msr_id,
    document_id,
    invoice_sha256,
    recipient_email,
    channel,
    provider_reference,
    delivered_at,
    verified_by_id,
    verified_at,
    prepared_by_id,
    now=None,
):
    """Check candidate structure; never return a trusted delivery result."""
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("now must be a timezone-aware datetime.")
    current = current.astimezone(timezone.utc)

    msr = _uuid(msr_id, "msr_id")
    document = _uuid(document_id, "document_id")
    verifier = _uuid(verified_by_id, "verified_by_id")
    preparer = _uuid(prepared_by_id, "prepared_by_id")
    if verifier == preparer:
        raise ValueError("The delivery verifier must differ from the preparer.")

    if not isinstance(invoice_sha256, str) or not _HEX_SHA256.fullmatch(invoice_sha256):
        raise ValueError("invoice_sha256 must contain 64 hexadecimal characters.")
    if not isinstance(recipient_email, str) or (
        not recipient_email.strip()
        or recipient_email.strip() != recipient_email
        or recipient_email.count("@") != 1
        or any(ch.isspace() for ch in recipient_email)
    ):
        raise ValueError("A valid recipient email is required.")
    if not isinstance(channel, str) or channel not in _CHANNELS:
        raise ValueError("An approved delivery channel is required.")
    if not isinstance(provider_reference, str) or not provider_reference.strip():
        raise ValueError("A nonempty provider receipt reference is required.")
    if provider_reference != provider_reference.strip() or len(provider_reference) > 256:
        raise ValueError("Provider reference has invalid surrounding space or length.")

    delivery_time = _aware(delivered_at, "delivered_at", current)
    verification_time = _aware(verified_at, "verified_at", current)
    if verification_time < delivery_time:
        raise ValueError("Verification cannot precede claimed delivery.")

    return DeliveryEvidenceCandidate(
        msr_id=msr,
        document_id=document,
        invoice_sha256=invoice_sha256.lower(),
        recipient_email=recipient_email,
        channel=channel,
        provider_reference=provider_reference,
        delivered_at=delivery_time,
        verified_by_id=verifier,
        verified_at=verification_time,
    )

# VERIDIAN PROVIDER OBSERVATION PREFLIGHT 4014
from collections.abc import Mapping


def preflight_provider_observation(
    observation,
    *,
    expected_account_id,
    expected_envelope_id,
    expected_document_id,
    expected_recipient_id,
    expected_recipient_email,
):
    """Match a provider-shaped observation, NEVER verify its authenticity.

    The expected values must come from independent trusted records.
    This function performs no provider lookup, permission check or write.
    A True match is NOT delivery evidence and grants no installation rights.
    """
    if not isinstance(observation, Mapping):
        return False

    def valid_id(value):
        if not isinstance(value, str):
            return None
        try:
            return str(UUID(value))
        except (ValueError, AttributeError, TypeError):
            return None

    for key, expected in (
        ("account_id", expected_account_id),
        ("envelope_id", expected_envelope_id),
        ("document_id", expected_document_id),
    ):
        actual_id = valid_id(observation.get(key))
        expected_id = valid_id(expected)
        if actual_id is None or expected_id is None or actual_id != expected_id:
            return False

    recipient_id = observation.get("recipient_id")
    if (
        not isinstance(recipient_id, str)
        or not isinstance(expected_recipient_id, str)
        or not recipient_id
        or recipient_id != expected_recipient_id
    ):
        return False

    email = observation.get("recipient_email")
    if (
        not isinstance(email, str)
        or not isinstance(expected_recipient_email, str)
        or not email
        or email.strip() != email
        or expected_recipient_email.strip() != expected_recipient_email
        or email.casefold() != expected_recipient_email.casefold()
    ):
        return False

    # A document-delivery event must have an explicit delivered status.
    # Other envelope lifecycle states are not substitutes.
    if observation.get("status") != "delivered":
        return False

    # Caller-provided trusted flags are never accepted as evidence.
    if observation.get("trusted_delivery") is not None:
        return False
    if observation.get("installation_evidence_accepted") is not None:
        return False
    return True
