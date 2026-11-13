"""Separate OAuth initiation for approved completion-envelope senders.

No callback dispatch, tokens, provider calls, or envelope sending.
Disabled by default and limited to isolated development databases.
"""
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign
from .completion_send_authorization_4620 import ACTION
from .completion_send_manifest_4619 import prepare_completion_send_manifest
from .completion_send_transaction_4623 import _verify_authorization_event
from .models import (
    AuditEvent, CompletionEnvelopeAttempt, DocusignChallenge,
    Project, Role,
)
from .services import audit


OPERATION = "SANDBOX_COMPLETION_SEND"


def _isolated():
    name = str(connection.settings_dict.get("NAME", "")).lower()
    if not (
        settings.DEBUG
        and settings.ENVIRONMENT == "development"
        and connection.vendor == "sqlite"
        and "memory" in name
        and os.getenv("GECC_TEST_COMPLETION_SEND_OAUTH") == "1"
    ):
        raise ValidationError(
            "Completion sender OAuth initiation is disabled."
        )


@transaction.atomic
def begin(*, actor, attempt_id, session_key):
    """Prepare one sender-specific challenge without contacting DocuSign."""
    _isolated()

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            not in (Role.SALES_MANAGER, Role.CEO)
    ):
        raise PermissionDenied(
            "Only an active Sales Manager or CEO can initiate sender OAuth."
        )

    if not isinstance(session_key, str) or not session_key:
        raise ValidationError("An authenticated session is required.")

    reference = CompletionEnvelopeAttempt.objects.select_related(
        "release_package__plan__msr"
    ).get(pk=attempt_id)

    project_id = reference.release_package.plan.msr.project_id
    Project.objects.select_for_update().get(pk=project_id)

    attempt = CompletionEnvelopeAttempt.objects.select_for_update().select_related(
        "initiated_by", "release_package__plan__msr__project"
    ).get(pk=attempt_id)

    if (
        attempt.state != "AUTH_PENDING"
        or attempt.first_send_started_at is not None
        or attempt.provider_envelope_id != ""
    ):
        raise ValidationError("Completion attempt is no longer unsent.")

    events = list(
        AuditEvent.objects.filter(
            action=ACTION,
            entity_id=project_id,
            payload__attempt_id=str(attempt.pk),
        ).order_by("sequence")[:2]
    )

    if len(events) != 1:
        raise ValidationError(
            "Exactly one prior send authorization is required."
        )

    event = events[0]
    _verify_authorization_event(event)

    if (
        event.actor_id != actor.pk
        or event.payload.get("authorizing_actor_id") != str(actor.pk)
        or event.payload.get("attempt_id") != str(attempt.pk)
        or event.payload.get("provider_account_id")
            != attempt.provider_account_id
        or event.payload.get("release_package_id")
            != str(attempt.release_package_id)
        or event.payload.get("release_package_digest")
            != attempt.release_package.digest
        or event.payload.get("live_send_authorized") is not False
    ):
        raise ValidationError("Sender authorization binding changed.")

    manifest = prepare_completion_send_manifest(
        actor=actor, attempt=attempt
    )

    if (
        manifest.attempt_id != str(attempt.pk)
        or manifest.release_package_id
            != str(attempt.release_package_id)
        or event.payload.get("document_sha256")
            != list(manifest.document_sha256)
        or event.payload.get("recipient_ids")
            != list(manifest.recipient_ids)
        or manifest.ready_for_live_send
        or manifest.envelope_sent
    ):
        raise ValidationError("Approved sender manifest changed.")

    config = docusign.configuration()

    if config["blockers"]:
        raise ValidationError(
            "DocuSign sandbox configuration is not ready."
        )

    try:
        account = str(UUID(config["account_id"]))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Configured account is invalid.") from None

    if (
        account != config["account_id"]
        or account != attempt.provider_account_id
    ):
        raise ValidationError("DocuSign sandbox account does not match.")

    existing = DocusignChallenge.objects.filter(
        context__operation=OPERATION,
        context__completion_attempt_id=str(attempt.pk),
    )

    if existing.exists():
        raise ValidationError(
            "Sender OAuth was already initiated for this attempt. "
            "Do not create another challenge automatically."
        )

    state = secrets.token_urlsafe(32)

    context = {
        "operation": OPERATION,
        "completion_attempt_id": str(attempt.pk),
        "project_id": str(project_id),
        "release_package_id": str(attempt.release_package_id),
        "release_package_digest": attempt.release_package.digest,
        "authorization_event_id": str(event.pk),
        "authorizing_actor_id": str(actor.pk),
        "account_id": account,
        "document_sha256": list(manifest.document_sha256),
        "recipient_ids": list(manifest.recipient_ids),
        "send_enabled": False,
    }

    challenge = DocusignChallenge.objects.create(
        actor=actor,
        state_digest=docusign.digest(state),
        session_digest=docusign.digest(session_key),
        configuration_digest=docusign.configuration_digest(config),
        expires_at=timezone.now() + timedelta(minutes=10),
        context=context,
    )

    audit(
        actor,
        "completion_envelope.sender_oauth_started",
        project_id,
        {
            "challenge_id": str(challenge.pk),
            "attempt_id": str(attempt.pk),
            "authorization_event_id": str(event.pk),
            "account_id": account,
            "network_request_permitted": False,
            "send_enabled": False,
        },
    )

    url = docusign.AUTH_ORIGIN + "/oauth/auth?" + urlencode({
        "response_type": "code",
        "scope": "signature",
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "state": state,
    })

    return {
        "authorization_url": url,
        "expires_at": challenge.expires_at.isoformat(),
        "operation": OPERATION,
        "send_enabled": False,
        "provider_authenticated": False,
        "envelope_sent": False,
    }
