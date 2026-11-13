"""Read-only completion signing manifest: NOT a sendable envelope.

Validates the approved release PDFs, recipient identities, GECC-first
routing, and provider-managed signature/date tabs. No provider calls,
database writes, or network-enabled payloads.
"""
import base64
import hashlib
from dataclasses import dataclass

from rest_framework.exceptions import ValidationError

from .completion_send_preflight_4618 import (
    require_completion_send_preflight,
)


@dataclass(frozen=True)
class CompletionSendManifest:
    attempt_id: str
    release_package_id: str
    project_id: str
    document_sha256: tuple
    recipient_ids: tuple
    signature_tabs_checked: bool
    signed_date_tabs_checked: bool
    ready_for_live_send: bool = False
    provider_authenticated: bool = False
    envelope_sent: bool = False
    completion_authorized: bool = False


def _require(condition, reason):
    if not condition:
        raise ValidationError(reason)


def prepare_completion_send_manifest(*, actor, attempt):
    gate = require_completion_send_preflight(
        actor=actor, attempt=attempt
    )

    package = attempt.release_package
    plan = package.plan
    review = plan.review
    payload = package.payload

    _require(
        isinstance(review, dict) and isinstance(payload, dict),
        "Signing and release records must be structured.",
    )

    preview = review.get("envelope_preview")
    entries = payload.get("documents")
    approved = review.get("documents")

    _require(
        isinstance(preview, dict)
        and isinstance(entries, list)
        and isinstance(approved, list)
        and len(entries) == len(approved) == 1,
        "Exactly one approved completion certificate PDF is required.",
    )

    _require(
        payload.get("purpose") == "UNSIGNED_RELEASE_REVIEW",
        "Only the approved unsigned release review may be inspected.",
    )

    _require(
        preview.get("status") == "created",
        "Only a never-sent DocuSign draft preview is allowed.",
    )

    preview_docs = preview.get("documents")
    _require(
        isinstance(preview_docs, list) and len(preview_docs) == 1,
        "Exactly one DocuSign document descriptor is required.",
    )

    entry = entries[0]
    reference = approved[0]
    descriptor = preview_docs[0]

    _require(
        all(isinstance(item, dict) for item in
            (entry, reference, descriptor)),
        "Document records are malformed.",
    )

    _require(
        entry.get("kind") == plan.group
        and reference.get("kind") == plan.group
        and descriptor.get("documentId") == "1"
        and descriptor.get("fileExtension") == "pdf"
        and descriptor.get("transformPdfFields") == "false"
        and isinstance(descriptor.get("name"), str)
        and bool(descriptor["name"].strip()),
        "Completion document identity or PDF settings changed.",
    )

    encoded = entry.get("documentBase64")
    _require(
        isinstance(encoded, str) and bool(encoded),
        "Release PDF bytes are missing.",
    )

    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError, base64.binascii.Error):
        raise ValidationError("Release PDF encoding is invalid.") from None

    digest = hashlib.sha256(content).hexdigest()

    _require(
        content.startswith(b"%PDF-")
        and len(content) > 8
        and digest == entry.get("pdf_sha256"),
        "Retained release PDF fingerprint is invalid.",
    )

    recipients = preview.get("recipients")
    signers = (
        recipients.get("signers")
        if isinstance(recipients, dict) else None
    )

    _require(
        isinstance(signers, list) and len(signers) == 2,
        "Exactly two approved signers are required.",
    )

    customer = review.get("customer")
    gecc = review.get("gecc")

    _require(
        isinstance(customer, dict) and isinstance(gecc, dict),
        "Reviewed signer identities are missing.",
    )

    _require(
        isinstance(customer.get("email"), str)
        and isinstance(gecc.get("email"), str)
        and customer["email"].strip().casefold()
            != gecc["email"].strip().casefold(),
        "Customer and GECC must have distinct signing emails.",
    )

    expected = {
        "1": (customer, "2", "customer"),
        "2": (gecc, "1", "gecc"),
    }

    observed_ids = set()

    for signer in signers:
        _require(isinstance(signer, dict), "Invalid signer record.")

        signer_id = signer.get("recipientId")
        _require(
            signer_id in expected and signer_id not in observed_ids,
            "Duplicate or unexpected signing recipient.",
        )
        observed_ids.add(signer_id)

        identity, order, prefix = expected[signer_id]

        _require(
            signer.get("routingOrder") == order
            and signer.get("name") == identity.get("name")
            and signer.get("email") == identity.get("email"),
            "Reviewed signer identity or routing order changed.",
        )

        tabs = signer.get("tabs")
        _require(
            isinstance(tabs, dict),
            "Signer signature and date tabs are required.",
        )

        for tab_type, required_label in (
            ("signHereTabs", prefix + "_signature"),
            ("dateSignedTabs", prefix + "_signed_date"),
            (
                "fullNameTabs",
                "customer_printed_name"
                if prefix == "customer"
                else "gecc_representative_name",
            ),
        ):
            items = tabs.get(tab_type)
            _require(
                isinstance(items, list) and len(items) == 1,
                "Exactly one required signature/name/date tab is needed.",
            )
            tab = items[0]
            _require(
                isinstance(tab, dict)
                and tab.get("documentId") == "1"
                and tab.get("recipientId") == signer_id
                and tab.get("tabLabel") == required_label,
                "Provider-managed signature/date tab identity changed.",
            )

            if tab_type == "signHereTabs":
                _require(
                    tab.get("optional") == "false",
                    "The signature may not be optional.",
                )

    _require(
        observed_ids == set(expected),
        "Customer and GECC signers must both be present.",
    )

    return CompletionSendManifest(
        attempt_id=gate.attempt_id,
        release_package_id=gate.release_package_id,
        project_id=gate.project_id,
        document_sha256=(digest,),
        recipient_ids=("1", "2"),
        signature_tabs_checked=True,
        signed_date_tabs_checked=True,
    )
