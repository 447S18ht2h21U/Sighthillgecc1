"""Read-only DocuSign demonstration-account retrieval gateway.

No envelope submission or modification. An OAuth bearer supplied by an
authorized caller is held only in memory; this component does not obtain,
store or print it. Returned metadata is not sufficient, by itself, to
verify a signature or authorize project completion.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from urllib.request import Request, build_opener
from uuid import UUID
import json
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied
from pypdf import PdfReader

from . import docusign
from .models import Role


@dataclass(frozen=True)
class SandboxInspectionReadback4972:
    account_id: str
    envelope_id: str
    envelope_summary: dict
    recipient_summary: dict
    recipient_tabs: dict
    signed_pdf: bytes
    certificate_pdf: bytes
    signed_pdf_sha256: str
    certificate_sha256: str
    audit_events: dict | None = None
    status: str = "SANDBOX_READBACK_NOT_INDEPENDENTLY_VERIFIED"
    provider_signature_verified: bool = False
    signer_identity_verified: bool = False
    inspection_findings_verified: bool = False
    completion_authorized: bool = False


def _uuid(value):
    try:
        canonical = str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Invalid provider identifier.") from None
    if type(value) is not str or value != canonical:
        raise ValidationError("Canonical provider UUID required.")
    return canonical


def _reader(path, token, *, pdf=False):
    """Allowlisted GET only; no redirects or user-selected network host."""
    # Match the COMPLETE canonical path, not a suffix or slash count.
    # Never accept queries, fragments, encoded separators, or extra paths.
    import re
    pattern = (
        r"/restapi/v2[.]1/accounts/"
        r"([0-9a-f-]{36})/envelopes/([0-9a-f-]{36})"
        r"(/recipients|/recipients/1/tabs|"
        r"/documents/1|/documents/certificate|/audit_events)?"
    )
    match = re.fullmatch(pattern, path) if type(path) is str else None
    if match is None:
        raise ValidationError("Provider retrieval path not permitted.")
    try:
        if (
            str(UUID(match.group(1))) != match.group(1)
            or str(UUID(match.group(2))) != match.group(2)
        ):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(
            "Canonical provider identity required."
        ) from None

    suffix = match.group(3) or ""
    if pdf is not (suffix in ("/documents/1", "/documents/certificate")):
        raise ValidationError(
            "Provider response type does not match endpoint."
        )
    request = Request(
        docusign.BASE_URI + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/pdf" if pdf else "application/json",
        },
        method="GET",
    )
    try:
        with build_opener(docusign.NoRedirects()).open(
            request, timeout=15
        ) as response:
            limit = 5_000_000 if pdf else 262144
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("Oversized provider response.")
        if pdf:
            if not raw.startswith(b"%PDF-"):
                raise ValueError("Not a PDF.")
            parsed = PdfReader(BytesIO(raw))
            if parsed.is_encrypted or not 1 <= len(parsed.pages) <= 150:
                raise ValueError("Unexpected PDF.")
            return raw
        decoded = json.loads(raw)
        if type(decoded) is not dict:
            raise ValueError("Unexpected JSON.")
        return decoded
    except Exception:
        raise ValidationError(
            "Read-only sandbox evidence retrieval failed."
        ) from None


def retrieve_inspection_sandbox_evidence(
    *,
    actor,
    account_id,
    envelope_id,
    bearer_token,
    reader=None,
):
    """Explicitly gated sandbox readback; never sends an envelope."""
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_IM_PROVIDER_READBACK_ENABLED") != "1"
    ):
        raise PermissionDenied("Inspection provider readback disabled.")
    if (
        actor is None
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None)
        not in (Role.CEO, Role.COMPTROLLER)
    ):
        raise PermissionDenied("Authorized reviewer required.")

    account_id = _uuid(account_id)
    envelope_id = _uuid(envelope_id)
    configured = docusign.configuration()
    if (
        type(configured) is not dict
        or configured.get("blockers")
        or configured.get("account_id") != account_id
        or docusign.BASE_URI != "https://demo.docusign.net"
    ):
        raise PermissionDenied("Verified sandbox configuration required.")

    if (
        type(bearer_token) is not str
        or not 16 <= len(bearer_token) <= 16384
        or any(c.isspace() for c in bearer_token)
    ):
        raise PermissionDenied("In-memory OAuth bearer required.")

    # Test transports must be explicitly supplied. Production transport
    # remains a fixed-origin, read-only network boundary.
    fetch = reader if reader is not None else _reader
    if not callable(fetch):
        raise ValidationError("Invalid retrieval transport.")

    base = (
        f"/restapi/v2.1/accounts/{account_id}"
        f"/envelopes/{envelope_id}"
    )
    summary = fetch(base, bearer_token)
    recipients = fetch(base + "/recipients", bearer_token)
    tabs = fetch(base + "/recipients/1/tabs", bearer_token)
    pdf = fetch(base + "/documents/1", bearer_token, pdf=True)
    certificate = fetch(
        base + "/documents/certificate", bearer_token, pdf=True
    )

    if (
        type(summary) is not dict
        or summary.get("envelopeId") != envelope_id
        or summary.get("status") != "completed"
        or type(recipients) is not dict
        or type(tabs) is not dict
        or type(pdf) is not bytes
        or type(certificate) is not bytes
        or pdf == certificate
    ):
        raise ValidationError("Incomplete provider-shaped readback.")

    for content in (pdf, certificate):
        if (
            not 100 <= len(content) <= 5_000_000
            or not content.startswith(b"%PDF-")
        ):
            raise ValidationError("Retrieved PDF integrity failed.")

    # Fixed, read-only DocuSign envelope audit history.
    # Event collection alone never verifies a signature.
    audit_path = (
        f"/restapi/v2.1/accounts/{account_id}"
        f"/envelopes/{envelope_id}/audit_events"
    )
    audit_events = reader(audit_path, bearer_token)

    if (
        type(audit_events) is not dict
        or type(audit_events.get("auditEvents")) is not list
        or not audit_events["auditEvents"]
        or len(audit_events["auditEvents"]) > 1000
        or any(
            type(item) is not dict
            or type(item.get("eventFields")) is not list
            for item in audit_events["auditEvents"]
        )
    ):
        raise ValidationError(
            "Incomplete provider envelope audit history."
        )

    return SandboxInspectionReadback4972(
        account_id=account_id,
        envelope_id=envelope_id,
        envelope_summary=summary,
        recipient_summary=recipients,
        audit_events=audit_events,
        recipient_tabs=tabs,
        signed_pdf=pdf,
        certificate_pdf=certificate,
        signed_pdf_sha256=sha256(pdf).hexdigest(),
        certificate_sha256=sha256(certificate).hexdigest(),
    )
