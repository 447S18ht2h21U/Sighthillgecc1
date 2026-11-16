"""Development-only DocuSign inspection draft transport.

No automatic activation, envelope sending, token retention,
database mutations, or project-completion authorization.
"""
import http.client
import json
import os
import re
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from core.installation_docusign_envelope_4962 import OfflineInstallationEnvelope
from core.installation_provider_oauth_4979 import Role


HOST = "demo.docusign.net"
ENABLED_FLAG = "GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED"
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$"
)


@dataclass(frozen=True)
class SandboxDraftCreation5173:
    account_id: str
    envelope_id: str
    status: str
    sent: bool = False
    signature_verified: bool = False
    completion_authorized: bool = False


def _uuid(value):
    if type(value) is not str or not _UUID.fullmatch(value.lower()):
        raise ValidationError("Valid DocuSign UUID required.")
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValidationError("Invalid DocuSign UUID.") from None


def _gate(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(ENABLED_FLAG) != "1"
    ):
        raise PermissionDenied("Sandbox draft creation disabled.")

    if (
        actor is None
        or not getattr(actor, "pk", None)
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None)
        not in (Role.CEO, Role.SALES_MANAGER)
    ):
        raise PermissionDenied("Authorized CEO or Sales Manager required.")


def _validate_draft_payload(request):
    if type(request) is not dict:
        raise ValidationError("Offline envelope request required.")

    if request.get("status") != "created":
        raise ValidationError("Only unsigned DocuSign drafts permitted.")

    if not all(
        key in request for key in ("documents", "recipients", "emailSubject")
    ):
        raise ValidationError("Incomplete inspection envelope request.")

    documents = request["documents"]
    recipients = request["recipients"]

    if type(documents) is not list or len(documents) != 1:
        raise ValidationError("Exactly one inspection document required.")

    document = documents[0]
    if (
        type(document) is not dict
        or document.get("documentId") != "1"
        or document.get("fileExtension") != "pdf"
        or type(document.get("documentBase64")) is not str
        or not document["documentBase64"]
    ):
        raise ValidationError("Invalid inspection document.")

    signers = recipients.get("signers") if type(recipients) is dict else None

    if type(signers) is not list or len(signers) != 1:
        raise ValidationError("Exactly one Installation Manager required.")

    signer = signers[0]
    if type(signer) is not dict or signer.get("recipientId") != "1":
        raise ValidationError("Invalid manager recipient.")

    tabs = signer.get("tabs")
    if (
        type(tabs) is not dict
        or len(tabs.get("radioGroupTabs", [])) != 5
        or len(tabs.get("signHereTabs", [])) != 1
        or len(tabs.get("dateSignedTabs", [])) != 1
    ):
        raise ValidationError("Inspection signing tabs incomplete.")

    return request


def create_sandbox_inspection_draft(
    *, actor, envelope, account_id, bearer_token
):
    """Create a provider DRAFT only, never send or claim signature trust.

    No caller is registered in an operational API at this stage.
    """
    _gate(actor)

    if type(envelope) is not OfflineInstallationEnvelope:
        raise ValidationError("Approved offline envelope object required.")

    if (
        envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.envelope_id is not None
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
    ):
        raise ValidationError("Offline draft safety contract failed.")

    request = _validate_draft_payload(envelope.request)
    account = _uuid(account_id)

    if (
        type(bearer_token) is not str
        or not 16 <= len(bearer_token) <= 16384
        or any(character.isspace() for character in bearer_token)
    ):
        raise PermissionDenied("Transient OAuth bearer token required.")

    from core import docusign
    configuration = docusign.configuration()

    if (
        type(configuration) is not dict
        or configuration.get("blockers")
        or configuration.get("account_id") != account
        or docusign.BASE_URI != "https://demo.docusign.net"
    ):
        raise PermissionDenied("Verified sandbox account required.")

    body = json.dumps(
        request, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")

    if len(body) > 10_000_000:
        raise ValidationError("Inspection draft exceeds transport limit.")

    path = f"/restapi/v2.1/accounts/{account}/envelopes"

    # Fixed host and fixed API operation; no arbitrary URL or redirects.
    connection = http.client.HTTPSConnection(HOST, timeout=15)

    try:
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Authorization": "Bearer " + bearer_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        response = connection.getresponse()
        content = response.read(65537)

        if len(content) > 65536:
            raise ValidationError("Oversized provider response.")

        if response.status not in (200, 201):
            raise ValidationError("Sandbox draft creation rejected.")

        try:
            result = json.loads(content)
        except (ValueError, UnicodeDecodeError):
            raise ValidationError("Malformed sandbox response.") from None

        if (
            type(result) is not dict
            or result.get("status") != "created"
        ):
            raise ValidationError("Provider did not confirm draft status.")

        envelope_id = _uuid(result.get("envelopeId"))

        return SandboxDraftCreation5173(
            account_id=account,
            envelope_id=envelope_id,
            status="created",
        )
    finally:
        connection.close()