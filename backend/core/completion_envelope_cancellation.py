"""Audited cancellation of attempts with no recorded sending activity."""
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from .models import CompletionEnvelopeAttempt, Role
from .services import audit
from .completion_envelope_states import require_transition

@transaction.atomic
def cancel_unsent_attempt(actor, attempt_id):
    if actor is None or not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or getattr(actor, "role", None) != Role.COMPTROLLER:
        raise PermissionDenied("Only an active Comptroller may cancel a completion attempt.")
    attempt = CompletionEnvelopeAttempt.objects.select_for_update().select_related("release_package__plan__msr").get(pk=attempt_id)
    next_state = require_transition(attempt.state, "CANCELLED_UNSENT", attempt.first_send_started_at)
    project_id = attempt.release_package.plan.msr.project_id
    attempt.state = next_state
    attempt.save(update_fields=["state"])
    audit(actor, "completion_envelope.cancelled_unsent", project_id, {"attempt_id": str(attempt.pk), "release_package_id": str(attempt.release_package_id), "state": next_state})
    return attempt
