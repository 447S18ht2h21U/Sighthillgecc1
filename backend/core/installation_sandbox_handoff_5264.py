"""Isolated-only, authorized DocuSign sandbox draft handoff.

Not registered as an API. The real provider boundary is disabled by
default. Never sends, signs, stores a token, or approves completion.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from core.installation_draft_handoff_5258 import verify_handoff
from core.installation_draft_browser_5185 import assemble
from core.installation_draft_authorization_5179 import _fingerprint
from core.installation_sandbox_draft_transport_5173 import (
    create_sandbox_inspection_draft,
)


@transaction.atomic
def create_authorized_sandbox_draft(
    *, actor, project_id, account_id, bearer_token
):
    # verify_handoff enforces the disposable in-memory database,
    # active CEO/Sales Manager, unique immutable authorization,
    # current approved MSR and exact server-generated fingerprint.
    verified = verify_handoff(
        actor=actor,
        project_id=project_id,
    )

    if (
        verified.get("project_id") != str(project_id)
        or verified.get("state") != "OFFLINE_DRAFT_HANDOFF_MATCHED"
        or verified.get("read_only") is not True
        or any(
            verified.get(flag) is not False
            for flag in (
                "provider_request_authorized",
                "provider_envelope_created",
                "send_authorized",
                "provider_signature_verified",
                "receipt_issuance_authorized",
                "project_completion_authorized",
            )
        )
    ):
        raise ValidationError(
            "Authorized inspection handoff not established."
        )

    # Independently regenerate and bind the exact request that would
    # cross the transport boundary. Never accept document bytes
    # or a signer supplied by the browser.
    envelope = assemble(actor=actor, project_id=project_id)

    if (
        _fingerprint(envelope)
        != verified.get("draft_payload_sha256")
        or envelope.project_id != str(project_id)
        or envelope.envelope_id is not None
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
    ):
        raise ValidationError(
            "Inspection package changed after authorization."
        )

    result = create_sandbox_inspection_draft(
        actor=actor,
        envelope=envelope,
        account_id=account_id,
        bearer_token=bearer_token,
    )

    if (
        result.status != "created"
        or result.sent is not False
        or result.signature_verified is not False
        or result.completion_authorized is not False
    ):
        raise ValidationError(
            "DocuSign sandbox did not confirm an unsent draft."
        )

    return result
