"""Bounded DocuSign sandbox transport, not connected to live sending.

Builds an actual REST request and parses a provider response.
Network execution is unavailable except with an explicitly supplied
test transport. No public API, automatic retry, or token retention.
"""
import base64
import hashlib
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import UUID

from rest_framework.exceptions import ValidationError

from . import docusign


MAX_REPLY_BYTES = 65536
SANDBOX_BASE = "https://demo.docusign.net"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _uuid(value):
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise ValidationError("Invalid DocuSign account or envelope ID.")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise ValidationError(
            "Invalid DocuSign account or envelope ID."
        ) from None
    return value


def prepare_sandbox_request(*, prepared, access_token):
    """Prepare one sandbox draft creation request; does not execute it."""
    account = _uuid(prepared.account_id)
    _uuid(prepared.attempt_id)

    if (
        prepared.send_available
        or prepared.provider_authenticated
        or prepared.envelope_sent
        or not isinstance(access_token, str)
        or not 20 <= len(access_token) <= 16384
        or "\n" in access_token
        or "\r" in access_token
    ):
        raise ValidationError("Sandbox transport request is not eligible.")

    payload = prepared.payload

    if (
        not isinstance(payload, dict)
        or payload.get("status") != "created"
        or payload.get("transactionId") != prepared.attempt_id
        or not isinstance(payload.get("documents"), list)
        or len(payload["documents"]) != 1
        or not isinstance(payload.get("recipients"), dict)
        or not isinstance(payload["recipients"].get("signers"), list)
        or len(payload["recipients"]["signers"]) < 2
        or not isinstance(prepared.document_sha256, tuple)
        or len(prepared.document_sha256) != 1
    ):
        raise ValidationError("Completion envelope payload is incomplete.")

    document = payload["documents"][0]

    if (
        not isinstance(document, dict)
        or document.get("documentId") != "1"
        or not isinstance(document.get("documentBase64"), str)
    ):
        raise ValidationError("Completion PDF descriptor is invalid.")

    try:
        raw = base64.b64decode(
            document["documentBase64"], validate=True
        )
    except (ValueError, TypeError, base64.binascii.Error):
        raise ValidationError(
            "Completion PDF encoding is invalid."
        ) from None

    if (
        not raw.startswith(b"%PDF-")
        or hashlib.sha256(raw).hexdigest()
            != prepared.document_sha256[0]
    ):
        raise ValidationError("Completion PDF fingerprint mismatch.")

    recipients = payload["recipients"]["signers"]
    recipient_ids = [item.get("recipientId") for item in recipients]
    emails = [item.get("email") for item in recipients]

    if (
        any(not isinstance(item, dict) for item in recipients)
        or any(not isinstance(value, str) or not value
                for value in recipient_ids)
        or len(set(recipient_ids)) != len(recipient_ids)
        or any(not isinstance(value, str) or "@" not in value
                for value in emails)
    ):
        raise ValidationError("Completion recipient manifest is invalid.")

    url = (
        SANDBOX_BASE
        + "/restapi/v2.1/accounts/"
        + account
        + "/envelopes"
    )
    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or parsed.netloc != "demo.docusign.net"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path !=
            "/restapi/v2.1/accounts/" + account + "/envelopes"
    ):
        raise ValidationError("DocuSign destination is not permitted.")

    body = json.dumps(
        payload, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )

    return request


def _parse_draft_reply(raw, *, account_id):
    """Validate a synthetic draft response without trusting it as proof."""
    _uuid(account_id)

    if not isinstance(raw, bytes) or len(raw) > MAX_REPLY_BYTES:
        raise ValidationError("Invalid DocuSign response size.")

    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValidationError(
            "Invalid DocuSign response encoding."
        ) from None

    if not isinstance(parsed, dict):
        raise ValidationError("Invalid DocuSign response.")

    envelope_id = _uuid(parsed.get("envelopeId"))

    if parsed.get("status") != "created":
        raise ValidationError(
            "Unexpected DocuSign envelope state. "
            "Do not retry the request automatically."
        )

    if (
        "accountId" in parsed
        and parsed["accountId"] != account_id
    ):
        raise ValidationError("DocuSign account identity mismatch.")

    return {
        "provider_envelope_id": envelope_id,
        "provider_status": "created",
        "provider_authenticated": False,
        "envelope_sent": False,
        "completion_authorized": False,
        "retry_allowed": False,
    }


def simulate_sandbox_draft_post(
    *, prepared, access_token, test_transport=None
):
    """Exercise a synthetic request only in an isolated test database.

    This must not be used as a production transport or an actual send.
    """
    import os
    from django.conf import settings
    from django.db import connection

    database_name = str(
        connection.settings_dict.get("NAME", "")
    ).lower()

    if not (
        settings.DEBUG
        and settings.ENVIRONMENT == "development"
        and connection.vendor == "sqlite"
        and "memory" in database_name
        and os.getenv("GECC_TEST_COMPLETION_TRANSPORT") == "1"
    ):
        raise ValidationError(
            "Completion provider transport is disabled."
        )

    if test_transport is None:
        raise ValidationError(
            "Provider network transport is not activated."
        )

    request = prepare_sandbox_request(
        prepared=prepared, access_token=access_token
    )

    # The test transport must be supplied explicitly. Never log the
    # request: its headers contain an access token and its body a PDF.
    try:
        response = test_transport(request)
        with response:
            if response.status != 201:
                raise ValueError("Unexpected provider response status.")
            raw = response.read(MAX_REPLY_BYTES + 1)
    except Exception:
        raise ValidationError(
            "Sandbox provider response failed. "
            "Do not retry automatically."
        ) from None

    return _parse_draft_reply(raw, account_id=prepared.account_id)
