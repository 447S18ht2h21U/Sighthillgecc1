"""Development-only DocuSign read of a candidate expedited signing bundle.

Must be invoked only from an independently authenticated OAuth callback
with a short-lived provider token. Never sends, persists trusted evidence,
or authorizes installation. Not registered as a user-facing endpoint.
"""
from uuid import UUID

from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign, signing_test
from .expedited_customer_document_validation_4566 import (
    validate_candidate_expedited_bundle,
)


def read_expedited_candidate(*, account_id, envelope_id, token, expected):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Customer signing retrieval is not live-enabled.")

    if not isinstance(expected, dict):
        raise ValidationError("Approved signing expectation required.")

    try:
        account = str(UUID(account_id))
        envelope = str(UUID(envelope_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid provider identifiers.") from None

    if account_id != account or envelope_id != envelope:
        raise ValidationError("Canonical provider identifiers required.")

    config = docusign.configuration()
    if config.get("blockers") or config.get("account_id") != account:
        raise PermissionDenied("Configured sandbox account is not ready.")

    if expected.get("envelope_id") != envelope:
        raise ValidationError("Expected envelope identity mismatch.")

    if not isinstance(token, str) or not 1 <= len(token) <= 16384:
        raise ValidationError("An authenticated provider session is required.")

    # These existing functions restrict the host, paths, redirects and
    # response sizes. No sending operation is permitted here.
    summary = signing_test.provider(account, envelope, token)
    recipients = signing_test.provider(
        account, envelope, token, resource="/recipients?include_tabs=true",
    )
    documents = signing_test.provider(
        account, envelope, token, resource="/documents",
    )

    # Fetch the exact two candidate signed PDFs and completion certificate.
    pdfs = {
        document_id: signing_test.pdf_document(
            account, envelope, document_id, token,
        )
        for document_id in ("1", "2", "certificate")
    }

    candidate = validate_candidate_expedited_bundle(
        expected=expected,
        summary=summary,
        recipients=recipients,
        documents=documents,
        signed_pdfs=pdfs,
    )

    after = signing_test.provider(account, envelope, token)
    if not isinstance(summary, dict) or not isinstance(after, dict):
        raise ValidationError("Provider envelope observation incomplete.")

    keys = (
        "envelopeId", "status", "lastModifiedDateTime",
        "completedDateTime",
    )
    if any(summary.get(key) != after.get(key) for key in keys):
        raise ValidationError(
            "Provider envelope changed during verification; retry the read."
        )

    # Even successful authenticated retrieval is only a candidate until
    # the approved MSR, signing plan and retention records are bound.
    return {
        **candidate,
        "retrieved_from_sandbox": True,
        "provider_authenticated": False,
        "customer_initials_verified": False,
        "signed_expedited_document_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
