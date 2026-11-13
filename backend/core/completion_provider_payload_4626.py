"""Validated DocuSign completion envelope assembly, without sending.

Sensitive payload includes approved PDF bytes. Never log or audit the
payload itself. No provider request, token, or database write occurs.
"""
import base64
import copy
import hashlib
from dataclasses import dataclass

from rest_framework.exceptions import ValidationError

from .completion_send_manifest_4619 import (
    prepare_completion_send_manifest,
)


@dataclass(frozen=True)
class PreparedCompletionEnvelope:
    attempt_id: str
    account_id: str
    payload: dict
    document_sha256: tuple
    send_available: bool = False
    provider_authenticated: bool = False
    envelope_sent: bool = False


def build_completion_envelope(*, actor, attempt):
    """Build a never-sent request from the current approved release."""
    manifest = prepare_completion_send_manifest(
        actor=actor,
        attempt=attempt,
    )
    package = attempt.release_package

    review = package.plan.review
    release_payload = package.payload

    preview = review.get("envelope_preview")
    entries = release_payload.get("documents")

    if (
        not isinstance(preview, dict)
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(entries[0], dict)
        or preview.get("status") != "created"
        or manifest.attempt_id != str(attempt.pk)
        or manifest.release_package_id != str(package.pk)
        or len(manifest.document_sha256) != 1
        or not manifest.signature_tabs_checked
        or not manifest.signed_date_tabs_checked
        or manifest.ready_for_live_send
        or manifest.envelope_sent
        or manifest.completion_authorized
    ):
        raise ValidationError(
            "The reviewed completion send manifest has changed."
        )

    envelope = copy.deepcopy(preview)
    documents = envelope.get("documents")

    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
        or documents[0].get("documentId") != "1"
    ):
        raise ValidationError(
            "The reviewed DocuSign document descriptor changed."
        )

    source = entries[0]
    encoded = source.get("documentBase64")

    if not isinstance(encoded, str) or not encoded:
        raise ValidationError("Approved completion PDF is missing.")

    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError, base64.binascii.Error):
        raise ValidationError(
            "Approved completion PDF encoding is invalid."
        ) from None

    digest = hashlib.sha256(content).hexdigest()

    if (
        not content.startswith(b"%PDF-")
        or digest != source.get("pdf_sha256")
        or digest != manifest.document_sha256[0]
    ):
        raise ValidationError(
            "Approved completion PDF bytes do not match the manifest."
        )

    if documents[0].get("documentBase64") not in (None, ""):
        raise ValidationError(
            "Signing preview unexpectedly includes document bytes."
        )

    documents[0]["documentBase64"] = encoded

    # Preserve the exact reviewed routing and provider-managed tabs.
    # Do not populate dates or signatures and do not mark status sent.
    envelope["status"] = "created"
    envelope["transactionId"] = str(attempt.pk)

    return PreparedCompletionEnvelope(
        attempt_id=str(attempt.pk),
        account_id=attempt.provider_account_id,
        payload=envelope,
        document_sha256=(digest,),
    )
