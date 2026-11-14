"""Offline Microsoft Graph Receipt request preparation.

No network transport, token acquisition, provider authentication,
customer delivery verification, or project-completion authority.
"""

import base64
import hashlib
import re
from dataclasses import dataclass
from urllib.parse import quote

from django.core.exceptions import ValidationError


SENDER = "care@gecc.cloud"
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HASH_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True)
class GraphReceiptPreview:
    endpoint: str
    request_body: dict
    pdf_sha256: str
    approved_msr_id: str
    recipient: str
    status: str = "PREVIEW_ONLY_NOT_SUBMITTED"
    submission_accepted: bool = False
    provider_authenticated: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def _email(value):
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not EMAIL_PATTERN.fullmatch(value)
    ):
        raise ValidationError("Valid, exact email address required.")
    return value.casefold()


def prepare_graph_receipt_preview(
    *,
    pdf_bytes,
    expected_sha256,
    recipient,
    approved_email,
    approved_msr_id,
    document_msr_id,
    document_kind,
    document_status,
    mode="PREVIEW_ONLY",
):
    """Build an unsent Microsoft Graph request for an eligible FINAL Receipt."""
    if mode != "PREVIEW_ONLY":
        raise ValidationError("Live Microsoft Graph Receipt sending is disabled.")

    if _email(recipient) != _email(approved_email):
        raise ValidationError("Recipient differs from the approved MSR.")

    if (
        not isinstance(approved_msr_id, str)
        or not approved_msr_id.strip()
        or approved_msr_id != document_msr_id
    ):
        raise ValidationError("FINAL Receipt MSR binding mismatch.")

    if document_kind != "RECEIPT" or document_status != "FINAL":
        raise ValidationError("Only an explicitly FINAL Receipt may be prepared.")

    if (
        not isinstance(pdf_bytes, bytes)
        or not pdf_bytes.startswith(b"%PDF-")
        or not pdf_bytes.rstrip().endswith(b"%%EOF")
    ):
        raise ValidationError("Complete retained PDF bytes required.")

    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if (
        not isinstance(expected_sha256, str)
        or not HASH_PATTERN.fullmatch(expected_sha256)
        or digest != expected_sha256.lower()
    ):
        raise ValidationError("Retained Receipt fingerprint mismatch.")

    body = {
        "message": {
            "subject": "Green Energy Contracting Corporation - Final Receipt",
            "body": {
                "contentType": "Text",
                "content": "Attached is your final project Receipt.",
            },
            "toRecipients": [{
                "emailAddress": {"address": recipient}
            }],
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": "Receipt.pdf",
                "contentType": "application/pdf",
                "contentBytes": base64.b64encode(pdf_bytes).decode("ascii"),
            }],
        },
        "saveToSentItems": True,
    }

    return GraphReceiptPreview(
        endpoint=(
            "https://graph.microsoft.com/v1.0/users/"
            + quote(SENDER, safe="")
            + "/sendMail"
        ),
        request_body=body,
        pdf_sha256=digest,
        approved_msr_id=approved_msr_id,
        recipient=recipient,
    )


def classify_graph_submission(http_status):
    """Graph 202 means accepted for processing, never delivered."""
    if type(http_status) is not int:
        raise ValidationError("HTTP status must be an integer.")
    return {
        "status": (
            "SUBMISSION_ACCEPTED_DELIVERY_UNVERIFIED"
            if http_status == 202 else "SUBMISSION_NOT_ACCEPTED"
        ),
        "provider_authenticated": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }
