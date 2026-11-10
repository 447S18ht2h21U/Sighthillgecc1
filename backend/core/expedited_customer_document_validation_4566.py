"""Validate candidate expedited DocuSign document metadata.

Only a separately authenticated provider retrieval can establish origin.
This function never creates trusted evidence or installation authority.
"""
from datetime import date
from uuid import UUID

from rest_framework.exceptions import ValidationError

from .completion_signature_validation import (
    validate_signed_pdf_bundle,
    verified_timestamp,
)


def validate_candidate_expedited_bundle(
    *, expected, summary, recipients, documents, signed_pdfs,
):
    if not isinstance(expected, dict):
        raise ValidationError("Approved expedited signing plan required.")

    required = (
        "envelope_id", "msr_id", "msr_version", "snapshot_sha256",
        "proposed_date", "customer_name", "customer_email",
    )
    if any(not expected.get(key) for key in required):
        raise ValidationError("Incomplete approved signing plan.")

    try:
        envelope_id = str(UUID(expected["envelope_id"]))
        proposed_date = date.fromisoformat(expected["proposed_date"])
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid signing identifiers or date.") from None

    if envelope_id != expected["envelope_id"]:
        raise ValidationError("Noncanonical envelope identifier.")

    if not isinstance(summary, dict) or (
        summary.get("envelopeId") != envelope_id
        or summary.get("status") != "completed"
    ):
        raise ValidationError("Expected envelope has not completed.")

    completed_at = verified_timestamp(summary.get("completedDateTime"))

    if not isinstance(recipients, dict):
        raise ValidationError("Missing recipient metadata.")

    signers = recipients.get("signers")
    if not isinstance(signers, list) or len(signers) != 1:
        raise ValidationError("Exactly one customer signer required.")

    customer = signers[0]
    if not isinstance(customer, dict) or any((
        customer.get("name") != expected["customer_name"],
        str(customer.get("email", "")).casefold()
            != str(expected["customer_email"]).casefold(),
        customer.get("status") != "completed",
    )):
        raise ValidationError("Customer identity or status mismatch.")

    signed_at = verified_timestamp(customer.get("signedDateTime"))
    if signed_at > completed_at:
        raise ValidationError("Signature exceeds envelope completion.")

    tabs = customer.get("tabs")
    if not isinstance(tabs, dict):
        raise ValidationError("Missing customer signing tabs.")

    initials = tabs.get("initialHereTabs")
    if not isinstance(initials, list) or len(initials) != 1:
        raise ValidationError("Required customer initials missing.")

    tab = initials[0]
    if not isinstance(tab, dict) or any((
        str(tab.get("documentId")) != "1",
        str(tab.get("tabLabel")) != "proposed-install-date-initials",
        str(tab.get("optional")).lower() != "false",
        not str(tab.get("pageNumber", "")).isdigit(),
    )):
        raise ValidationError("Customer initials tab does not match SOW.")

    # Candidate metadata only; trusted provider provenance is still required.
    date_tabs = tabs.get("textTabs")
    if not isinstance(date_tabs, list) or len(date_tabs) != 1:
        raise ValidationError("Proposed installation date tab is missing.")

    date_tab = date_tabs[0]
    if not isinstance(date_tab, dict) or any((
        str(date_tab.get("documentId")) != "1",
        date_tab.get("tabLabel") != "proposed-install-date",
        date_tab.get("value") != proposed_date.isoformat(),
        str(date_tab.get("optional")).lower() != "false",
        str(date_tab.get("pageNumber")) != str(tab.get("pageNumber")),
    )):
        raise ValidationError("Initialed date does not match approved proposal.")

    try:
        dx = abs(float(date_tab["xPosition"]) - float(tab["xPosition"]))
        dy = abs(float(date_tab["yPosition"]) - float(tab["yPosition"]))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValidationError("Date and initials positions are invalid.") from None

    if dx > 240 or dy > 40:
        raise ValidationError("Initials are not beside the installation date.")

    signatures = tabs.get("signHereTabs")
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise ValidationError("Signed expedited request tab is missing.")

    signature = signatures[0]
    if not isinstance(signature, dict) or any((
        str(signature.get("documentId")) != "2",
        signature.get("tabLabel") != "expedited-service-customer-signature",
        str(signature.get("optional")).lower() != "false",
        not str(signature.get("pageNumber", "")).isdigit(),
    )):
        raise ValidationError("Expedited customer signature tab differs.")

    if not isinstance(documents, dict):
        raise ValidationError("Missing signed-document metadata.")

    observed = documents.get("envelopeDocuments")
    required_docs = {
        ("1", "PROJECT_SOW"),
        ("2", "REQUEST_FOR_EXPEDITED_SERVICE"),
    }
    if not isinstance(observed, list):
        raise ValidationError("Missing signed-document list.")

    identities = [
        (str(item.get("documentId")), str(item.get("name")))
        for item in observed
        if isinstance(item, dict)
        and str(item.get("documentId")) != "certificate"
    ]
    if len(observed) != len(identities) or (
        len(identities) != 2 or set(identities) != required_docs
    ):
        raise ValidationError("Signed-document identities mismatch.")

    hashes = validate_signed_pdf_bundle(["1", "2"], signed_pdfs)

    return {
        "status": "STRUCTURALLY_VALID_UNAUTHENTICATED_CANDIDATE",
        "envelope_id": envelope_id,
        "msr_id": expected["msr_id"],
        "msr_version": expected["msr_version"],
        "snapshot_sha256": expected["snapshot_sha256"],
        "proposed_date": proposed_date.isoformat(),
        "customer_signed_at": signed_at.isoformat(),
        "retained_document_hashes": hashes,
        "provider_authenticated": False,
        "customer_initials_verified": False,
        "signed_expedited_document_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
