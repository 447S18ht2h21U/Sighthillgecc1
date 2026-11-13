"""Restricted DocuSign sandbox completion-certificate retrieval.

The caller must eventually be the approved OAuth callback. This module
does not initiate OAuth, retain credentials, write evidence, or authorize
project completion. It cannot establish trusted provenance by itself.
"""
import json
from urllib.request import Request, build_opener
from uuid import UUID

from django.conf import settings
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import ValidationError

from . import docusign
from .completion_signature_validation import (
    validate_completed_envelope,
    validate_completed_signers,
    validate_signature_tabs,
    validate_completion_documents,
    validate_signed_pdf_bundle,
)

MAX_JSON = 1024 * 1024
MAX_PDF = 8 * 1024 * 1024


def _uuid(value):
    try:
        parsed = str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Canonical DocuSign identifier required.") from None
    if parsed != value:
        raise ValidationError("Canonical DocuSign identifier required.")
    return parsed


def _sandbox():
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError(
            "Completion provider reads are restricted to development sandbox."
        )


@sensitive_variables("token")
def _read(path, token, *, pdf=False):
    if not isinstance(token, str) or not 1 <= len(token) <= 16384:
        raise ValidationError("Authenticated provider access is required.")
    if not path.startswith("/restapi/v2.1/accounts/"):
        raise ValidationError("Unsupported provider path.")

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
            request, timeout=12
        ) as response:
            content = response.read((MAX_PDF if pdf else MAX_JSON) + 1)
            content_type = response.headers.get(
                "Content-Type", ""
            ).split(";", 1)[0].strip().lower()

        if pdf:
            if (
                len(content) > MAX_PDF
                or content_type != "application/pdf"
                or not content.startswith(b"%PDF-")
            ):
                raise ValueError()
            return content

        if len(content) > MAX_JSON or content_type != "application/json":
            raise ValueError()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError()
        return parsed

    except Exception:
        raise ValidationError(
            "DocuSign completion retrieval or provider response validation failed."
        ) from None


@sensitive_variables("token")
def read_completed_certificate(
    *,
    account_id,
    envelope_id,
    token,
    expected,
    retain_bytes=False,
):
    """Fetch and validate one completed sandbox envelope.

    Caller-controlled metadata cannot replace an authenticated OAuth
    connection. The result is deliberately NOT completion authority.
    """
    _sandbox()
    if type(retain_bytes) is not bool:
        raise ValidationError("Invalid PDF retention mode.")
    account = _uuid(account_id)
    envelope = _uuid(envelope_id)

    config = docusign.configuration()
    if config["blockers"] or config["account_id"] != account:
        raise ValidationError(
            "Completion verification requires the configured sandbox account."
        )

    if not isinstance(token, str) or not 1 <= len(token) <= 16384:
        raise ValidationError("Authenticated provider access is required.")

    if not isinstance(expected, dict):
        raise ValidationError("Approved signing plan is required.")

    documents = expected.get("documents")
    if not isinstance(documents, list) or not 1 <= len(documents) <= 8:
        raise ValidationError("Approved document list is invalid.")

    ids = [item.get("documentId") if isinstance(item, dict) else None
           for item in documents]

    if (
        any(not isinstance(item, str) or
            not item.isascii() or
            not item.isdecimal() or
            len(item) > 8 or
            int(item) < 1
            for item in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValidationError("Approved document IDs are invalid.")

    base = (
        f"/restapi/v2.1/accounts/{account}/envelopes/{envelope}"
    )

    summary = _read(base, token)
    confirmation = validate_completed_envelope(
        envelope, summary
    )

    recipients = _read(
        base + "/recipients?include_tabs=true", token
    )
    signers = validate_completed_signers(
        expected, recipients, confirmation["completed_at"]
    )
    validate_signature_tabs(expected, recipients)

    provider_documents = _read(base + "/documents", token)
    verified_documents = validate_completion_documents(
        expected, provider_documents
    )

    pdfs = {}
    for document_id in [*ids, "certificate"]:
        pdfs[document_id] = _read(
            base + "/documents/" + document_id,
            token,
            pdf=True,
        )

    manifest = validate_signed_pdf_bundle(ids, pdfs)

    return {
        "provider": "DOCUSIGN_SANDBOX",
        "account_id": account,
        "envelope_id": envelope,
        "completed_at": confirmation["completed_at"],
        "signers": signers,
        "documents": verified_documents,
        "pdf_manifest": manifest,
        **({"_validated_pdf_bytes": pdfs} if retain_bytes else {}),
        "provider_response_validated": True,
        "oauth_callback_binding_verified": False,
        "persisted_evidence_verified": False,
        "receipt_email_authenticated": False,
        "completion_authorized": False,
        "project_completed": False,
    }
