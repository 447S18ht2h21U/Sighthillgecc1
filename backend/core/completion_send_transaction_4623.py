"""Isolated transaction acceptance for completion-envelope send intent.

This module makes NO provider requests. It must never be used as a live
send operation. Its isolation gate is intentionally independent of the
normal development environment and disabled by default.
"""
import hashlib
import json
import os

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .completion_send_authorization_4620 import ACTION
from .completion_send_lifecycle_4621 import (
    require_send_start_decision,
)
from .completion_send_manifest_4619 import (
    prepare_completion_send_manifest,
)
from .documents import canonical_hash
from .models import AuditEvent, CompletionEnvelopeAttempt, Project
from .services import audit


def _require_isolated_test():
    database_name = str(connection.settings_dict.get("NAME", ""))
    if not (
        settings.DEBUG
        and settings.ENVIRONMENT == "development"
        and connection.vendor == "sqlite"
        and "memory" in database_name.lower()
        and os.getenv("GECC_TEST_COMPLETION_SEND_INTENT") == "1"
    ):
        raise ValidationError(
            "Completion send-intent simulation requires disposable "
            "in-memory SQLite and explicit test authorization."
        )


def _verify_authorization_event(event):
    """Recalculate the existing append-only audit-chain event digest."""
    body = {
        "sequence": event.sequence,
        "actor": str(event.actor_id),
        "action": event.action,
        "entity_id": str(event.entity_id),
        "payload": event.payload,
        "previous_hash": event.previous_hash,
    }
    digest = hashlib.sha256(
        json.dumps(
            body, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()

    if digest != event.digest:
        raise ValidationError(
            "Send authorization audit-event integrity failed."
        )

    payload = event.payload
    if not isinstance(payload, dict):
        raise ValidationError("Send authorization payload missing.")

    binding = payload.get("manifest_binding_sha256")
    unsigned = {
        key: value for key, value in payload.items()
        if key != "manifest_binding_sha256"
    }

    if (
        not isinstance(binding, str)
        or binding != canonical_hash(unsigned)
    ):
        raise ValidationError(
            "Send authorization manifest-binding integrity failed."
        )


@transaction.atomic
def reserve_isolated_send_intent(*, actor, attempt_id):
    """Persist a simulated first-send intent, never a network request."""
    _require_isolated_test()

    reference = (
        CompletionEnvelopeAttempt.objects
        .select_related("release_package__plan__msr")
        .get(pk=attempt_id)
    )
    project_id = reference.release_package.plan.msr.project_id

    Project.objects.select_for_update().get(pk=project_id)

    attempt = (
        CompletionEnvelopeAttempt.objects
        .select_for_update()
        .select_related(
            "initiated_by",
            "release_package__plan__msr__project",
        )
        .get(pk=attempt_id)
    )

    records = list(
        AuditEvent.objects.filter(
            action=ACTION,
            entity_id=project_id,
            payload__attempt_id=str(attempt.pk),
        ).order_by("sequence")[:2]
    )

    if len(records) != 1:
        raise ValidationError(
            "Exactly one durable authorization is required."
        )

    event = records[0]
    _verify_authorization_event(event)

    manifest = prepare_completion_send_manifest(
        actor=actor, attempt=attempt
    )

    decision = require_send_start_decision(
        actor=actor,
        attempt=attempt,
        authorization_event=event,
        manifest=manifest,
    )

    if (
        decision.next_state != "NETWORK_STARTED"
        or not decision.first_send_required
        or decision.retry_allowed
        or decision.network_request_permitted
        or decision.completion_authorized
        or decision.provider_envelope_id != ""
    ):
        raise ValidationError(
            "First-send decision cannot permit an actual network request."
        )

    attempt.state = "NETWORK_STARTED"
    attempt.first_send_started_at = timezone.now()
    attempt.save(
        update_fields=["state", "first_send_started_at"]
    )

    audit(
        actor,
        "completion_envelope.isolated_send_intent_reserved",
        project_id,
        {
            "attempt_id": str(attempt.pk),
            "authorization_event_id": str(event.pk),
            "release_package_id": str(attempt.release_package_id),
            "state": "NETWORK_STARTED",
            "network_request_permitted": False,
            "provider_envelope_id": "",
            "test_only": True,
        },
    )

    return {
        "attempt_id": str(attempt.pk),
        "state": "NETWORK_STARTED",
        "network_request_permitted": False,
        "retry_allowed": False,
        "provider_envelope_id": "",
        "provider_authenticated": False,
        "completion_authorized": False,
    }
