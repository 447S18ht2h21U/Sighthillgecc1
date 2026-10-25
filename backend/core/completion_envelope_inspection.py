"""Read-only inspection of locally recorded completion-envelope attempts.

Local records are not authenticated provider evidence.
This module performs no network requests or database writes.
"""

from rest_framework.exceptions import PermissionDenied

from .models import CompletionEnvelopeAttempt, Role


def inspect_attempt(actor, attempt_id):
    """Return a restricted, read-only view of an existing attempt."""
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied(
            "Only an active Comptroller may inspect completion-envelope attempts."
        )

    attempt = (
        CompletionEnvelopeAttempt.objects
        .select_related("release_package__plan__msr")
        .get(pk=attempt_id)
    )

    package = attempt.release_package

    return {
        "attempt_id": str(attempt.pk),
        "project_id": str(package.plan.msr.project_id),
        "release_package_id": str(package.pk),
        "release_package_digest": package.digest,
        "provider_account_id": attempt.provider_account_id,
        "provider_envelope_id": attempt.provider_envelope_id or None,
        "state": attempt.state,
        "created_at": attempt.created_at.isoformat(),
        "first_send_started_at": (
            attempt.first_send_started_at.isoformat()
            if attempt.first_send_started_at else None
        ),
        "provider_authenticated": False,
        "signature_completion_verified": False,
        "send_available": False,
    }
