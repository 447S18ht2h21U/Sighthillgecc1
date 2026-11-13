"""Isolated synthetic provider-response persistence.

Does not contact DocuSign, authenticate a provider response, send an
envelope, or assert that any actual envelope exists. This is exclusively
a transactional regression harness for the future provider adapter.
"""
import hashlib
import json

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .completion_send_transaction_4623 import _require_isolated_test
from .completion_send_lifecycle_4621 import (
    require_provider_outcome_decision,
)
from .models import (
    AuditEvent, CompletionEnvelopeAttempt, Project, Role,
)
from .services import audit


INTENT_ACTION = "completion_envelope.isolated_send_intent_reserved"
RESPONSE_ACTION = "completion_envelope.isolated_provider_response_recorded"


def _verify_event(event):
    body = {
        "sequence": event.sequence,
        "actor": str(event.actor_id),
        "action": event.action,
        "entity_id": str(event.entity_id),
        "payload": event.payload,
        "previous_hash": event.previous_hash,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if event.digest != digest:
        raise ValidationError("Send-intent audit integrity changed.")


@transaction.atomic
def record_isolated_response(
    *, actor, attempt_id, outcome, provider_envelope_id=None
):
    """Simulate one outcome, with no provider access or live authority."""
    _require_isolated_test()

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            not in (Role.SALES_MANAGER, Role.CEO)
    ):
        raise PermissionDenied("Unauthorized completion send actor.")

    reference = CompletionEnvelopeAttempt.objects.select_related(
        "release_package__plan__msr"
    ).get(pk=attempt_id)

    project_id = reference.release_package.plan.msr.project_id
    Project.objects.select_for_update().get(pk=project_id)

    attempt = CompletionEnvelopeAttempt.objects.select_for_update().get(
        pk=attempt_id
    )

    intents = list(
        AuditEvent.objects.filter(
            action=INTENT_ACTION,
            entity_id=project_id,
            payload__attempt_id=str(attempt.pk),
        ).order_by("sequence")[:2]
    )

    if len(intents) != 1:
        raise ValidationError("Exactly one recorded send intent required.")

    event = intents[0]
    _verify_event(event)

    if (
        event.actor_id != actor.pk
        or event.payload.get("authorization_event_id") is None
        or event.payload.get("release_package_id")
            != str(attempt.release_package_id)
        or event.payload.get("state") != "NETWORK_STARTED"
        or event.payload.get("network_request_permitted") is not False
        or event.payload.get("test_only") is not True
    ):
        raise ValidationError("Send-intent actor or identity changed.")

    existing = AuditEvent.objects.filter(
        action=RESPONSE_ACTION,
        entity_id=project_id,
        payload__attempt_id=str(attempt.pk),
    )
    if existing.exists():
        raise ValidationError("Provider response already recorded.")

    decision = require_provider_outcome_decision(
        attempt=attempt,
        outcome=outcome,
        provider_envelope_id=provider_envelope_id,
    )

    if (
        decision.attempt_id != str(attempt.pk)
        or decision.first_send_required
        or decision.retry_allowed
        or decision.network_request_permitted
        or decision.completion_authorized
        or decision.next_state
            not in ("SENT_UNCHECKED", "SEND_UNCERTAIN")
    ):
        raise ValidationError("Invalid synthetic provider outcome.")

    attempt.state = decision.next_state
    attempt.provider_envelope_id = decision.provider_envelope_id
    attempt.save(update_fields=["state", "provider_envelope_id"])

    audit(
        actor,
        RESPONSE_ACTION,
        project_id,
        {
            "attempt_id": str(attempt.pk),
            "send_intent_event_id": str(event.pk),
            "release_package_id": str(attempt.release_package_id),
            "state": decision.next_state,
            "provider_envelope_id": decision.provider_envelope_id,
            "synthetic_provider_response": True,
            "provider_authenticated": False,
            "network_request_permitted": False,
            "retry_allowed": False,
            "completion_authorized": False,
        },
    )

    return {
        "attempt_id": str(attempt.pk),
        "state": decision.next_state,
        "provider_envelope_id": decision.provider_envelope_id,
        "synthetic_provider_response": True,
        "provider_authenticated": False,
        "network_request_permitted": False,
        "retry_allowed": False,
        "completion_authorized": False,
    }
