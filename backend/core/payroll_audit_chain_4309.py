"""Test-only read-only verification of the original GECC audit chain.

Recomputes the exact digest used by core.services.audit and checks
sequence continuity, the database audit head, and associated outbox
rows. This does NOT establish externally anchored authenticity.

No permissions, operational endpoints, or database mutations.
"""
import hashlib
import json

from .models import AuditEvent, AuditHead, Outbox


def _head():
    return list(AuditHead.objects.all())


def _events():
    return list(AuditEvent.objects.order_by("sequence"))


def _outboxes():
    return list(Outbox.objects.select_related("event").all())


def candidate_complete_audit_chain():
    """Return True only for one consistent nonempty audit chain."""
    heads = _head()
    if len(heads) != 1 or heads[0].pk != 1:
        return False

    head = heads[0]
    events = _events()

    if not events:
        return False

    previous = "0" * 64

    for expected_sequence, event in enumerate(events, start=1):
        if type(event.sequence) is not int:
            return False
        if event.sequence != expected_sequence:
            return False
        if event.previous_hash != previous:
            return False
        if type(event.payload) is not dict:
            return False
        if event.actor_id is None:
            return False

        body = {
            "sequence": event.sequence,
            "actor": str(event.actor_id),
            "action": event.action,
            "entity_id": str(event.entity_id),
            "payload": event.payload,
            "previous_hash": previous,
        }

        try:
            encoded = json.dumps(
                body, sort_keys=True, separators=(",", ":")
            ).encode()
        except (TypeError, ValueError, OverflowError):
            return False

        digest = hashlib.sha256(encoded).hexdigest()

        if event.digest != digest:
            return False

        previous = digest

    if head.sequence != len(events) or head.digest != previous:
        return False

    outboxes = _outboxes()

    if len(outboxes) != len(events):
        return False

    by_event = {}

    for outbox in outboxes:
        if outbox.event_id in by_event:
            return False
        if type(outbox.payload) is not dict:
            return False
        by_event[outbox.event_id] = outbox

    for event in events:
        outbox = by_event.get(event.pk)

        if outbox is None:
            return False
        if outbox.topic != event.action:
            return False
        if outbox.payload != {
            "audit_id": str(event.pk),
            "entity_id": str(event.entity_id),
        }:
            return False

    return True


def audit_chain_candidate_grants_live_access(*args, **kwargs):
    """Verifying the chain does not grant payroll access."""
    return False