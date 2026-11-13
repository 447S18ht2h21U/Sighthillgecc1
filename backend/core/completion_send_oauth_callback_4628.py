"""Dedicated completion sender OAuth callback; no envelope sending.

Only available under the isolated testing gate. The challenge is
consumed before any token exchange, preventing callback replay.
Tokens and authorization codes are never stored.
"""
import base64
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign
from .completion_send_oauth_4627 import OPERATION, _isolated
from .completion_send_authorization_4620 import ACTION
from .completion_send_transaction_4623 import (
    _verify_authorization_event,
)
from .completion_send_manifest_4619 import (
    prepare_completion_send_manifest,
)
from .documents import canonical_hash
from .models import (
    AuditEvent, CompletionEnvelopeAttempt, DocusignChallenge,
    DocusignVerification, Project, Role,
)
from .services import audit


def is_sender_state(state):
    """Recognize only a previously created sender OAuth challenge."""
    if not isinstance(state, str) or not 32 <= len(state) <= 128:
        return False

    return DocusignChallenge.objects.filter(
        state_digest=docusign.digest(state),
        context__operation=OPERATION,
    ).exists()


@transaction.atomic
def consume_sender_challenge(*, actor, session_key, state):
    _isolated()

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            not in (Role.SALES_MANAGER, Role.CEO)
    ):
        raise PermissionDenied(
            "Only an active Sales Manager or CEO can complete sender OAuth."
        )

    if (
        not isinstance(state, str)
        or not 32 <= len(state) <= 128
        or not isinstance(session_key, str)
        or not session_key
    ):
        raise ValidationError("Invalid sender OAuth callback.")

    config = docusign.configuration()

    if config["blockers"]:
        raise ValidationError("DocuSign sandbox configuration changed.")

    challenge = DocusignChallenge.objects.select_for_update().filter(
        state_digest=docusign.digest(state),
    ).first()

    if (
        challenge is None
        or challenge.consumed_at is not None
        or challenge.expires_at <= timezone.now()
        or challenge.actor_id != actor.pk
        or challenge.session_digest != docusign.digest(session_key)
        or challenge.configuration_digest
            != docusign.configuration_digest(config)
        or not isinstance(challenge.context, dict)
        or challenge.context.get("operation") != OPERATION
        or challenge.context.get("send_enabled") is not False
    ):
        raise ValidationError(
            "Sender OAuth challenge is invalid, expired, or used."
        )

    context = challenge.context

    reference = CompletionEnvelopeAttempt.objects.select_related(
        "release_package__plan__msr"
    ).get(pk=context["completion_attempt_id"])

    project_id = reference.release_package.plan.msr.project_id
    Project.objects.select_for_update().get(pk=project_id)

    attempt = CompletionEnvelopeAttempt.objects.select_for_update().select_related(
        "initiated_by",
        "release_package__plan__msr__project",
    ).get(pk=reference.pk)

    if (
        attempt.state != "AUTH_PENDING"
        or attempt.first_send_started_at is not None
        or attempt.provider_envelope_id != ""
        or config["account_id"] != attempt.provider_account_id
        or context.get("account_id") != attempt.provider_account_id
        or context.get("project_id") != str(project_id)
        or context.get("release_package_id")
            != str(attempt.release_package_id)
        or context.get("release_package_digest")
            != attempt.release_package.digest
        or context.get("authorizing_actor_id") != str(actor.pk)
    ):
        raise ValidationError("Sender OAuth binding is no longer current.")

    events = list(AuditEvent.objects.filter(
        action=ACTION,
        entity_id=project_id,
        payload__attempt_id=str(attempt.pk),
    ).order_by("sequence")[:2])

    if len(events) != 1:
        raise ValidationError("Exactly one send authorization is required.")

    event = events[0]
    _verify_authorization_event(event)

    manifest = prepare_completion_send_manifest(
        actor=actor,
        attempt=attempt,
    )

    if (
        event.pk.__str__() != context.get("authorization_event_id")
        or event.actor_id != actor.pk
        or event.payload.get("authorizing_actor_id") != str(actor.pk)
        or event.payload.get("release_package_digest")
            != attempt.release_package.digest
        or event.payload.get("live_send_authorized") is not False
        or context.get("document_sha256")
            != list(manifest.document_sha256)
        or context.get("recipient_ids")
            != list(manifest.recipient_ids)
        or event.payload.get("document_sha256")
            != list(manifest.document_sha256)
        or event.payload.get("recipient_ids")
            != list(manifest.recipient_ids)
        or manifest.attempt_id != str(attempt.pk)
        or manifest.project_id != str(project_id)
        or manifest.ready_for_live_send
        or manifest.envelope_sent
    ):
        raise ValidationError("Sender OAuth authorization or manifest changed.")

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at"])

    audit(
        actor,
        "completion_envelope.sender_oauth_consumed",
        project_id,
        {
            "challenge_id": str(challenge.pk),
            "attempt_id": str(attempt.pk),
            "authorization_event_id": str(event.pk),
            "send_enabled": False,
        },
    )

    return challenge, config, attempt


def finish(*, actor, session_key, state, code, error=None):
    """Authenticate sandbox identity; never create an envelope."""
    challenge, config, attempt = consume_sender_challenge(
        actor=actor, session_key=session_key, state=state,
    )

    if (
        error
        or not isinstance(code, str)
        or not code
        or len(code) > 16384
    ):
        raise ValidationError(
            "Sender OAuth was declined or incomplete. No send occurred."
        )

    basic = base64.b64encode(
        (config["client_id"] + ":" + config["client_secret"]).encode()
    ).decode()

    tokens = docusign.request_json(
        "/oauth/token",
        "Basic " + basic,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
        },
    )

    access_token = tokens.get("access_token")
    lifetime = tokens.get("expires_in")

    if (
        not isinstance(access_token, str)
        or not access_token
        or len(access_token) > 16384
        or str(tokens.get("token_type", "")).lower() != "bearer"
        or type(lifetime) is not int
        or not 0 < lifetime <= 86400
    ):
        raise ValidationError("Invalid sender OAuth token metadata.")

    info = docusign.request_json(
        "/oauth/userinfo", "Bearer " + access_token
    )

    accounts = info.get("accounts")

    if not isinstance(accounts, list):
        raise ValidationError("Sender OAuth account identity invalid.")

    matches = [
        row for row in accounts
        if isinstance(row, dict)
        and row.get("account_id") == config["account_id"]
        and row.get("base_uri") == docusign.BASE_URI
    ]

    if len(matches) != 1:
        raise ValidationError("Sender OAuth sandbox account mismatch.")

    try:
        subject = str(UUID(info.get("sub", "")))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Sender OAuth subject invalid.") from None

    identity = {
        "purpose": "SANDBOX_COMPLETION_SENDER_IDENTITY_ONLY",
        "environment": "SANDBOX",
        "account_id": config["account_id"],
        "client_id": config["client_id"],
        "subject": subject,
        "completion_attempt_id": str(attempt.pk),
        "authorization_challenge_id": str(challenge.pk),
        "verified_at": timezone.now().isoformat(),
        "tokens_retained": False,
        "send_enabled": False,
        "envelope_sent": False,
    }

    # Never store access tokens, refresh tokens or authorization codes.
    del tokens, access_token, basic, code, info

    with transaction.atomic():
        proof = DocusignVerification.objects.create(
            actor=actor,
            challenge=challenge,
            identity=identity,
            digest=canonical_hash(identity),
        )

        audit(
            actor,
            "completion_envelope.sender_identity_verified",
            attempt.release_package.plan.msr.project_id,
            {
                "verification_id": str(proof.pk),
                "challenge_id": str(challenge.pk),
                "attempt_id": str(attempt.pk),
                "send_enabled": False,
                "envelope_sent": False,
            },
        )

    return {
        "status": "SANDBOX_SENDER_IDENTITY_VERIFIED_NO_SEND",
        "verification_id": str(proof.pk),
        "send_enabled": False,
        "envelope_sent": False,
        "completion_authorized": False,
    }
