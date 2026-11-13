"""Completion-envelope send authorization; no sending or state changes.

Only an active Sales Manager or CEO can pass this gate. The existing
Comptroller-created attempt must remain tied to its current approved
release. Passing this gate never permits a provider call by itself.
"""
from dataclasses import dataclass
from uuid import UUID

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role


@dataclass(frozen=True)
class CompletionSendPreflight:
    attempt_id: str
    project_id: str
    release_package_id: str
    actor_id: str
    authority_validated: bool
    release_validated: bool
    live_sending_enabled: bool = False
    provider_authenticated: bool = False
    envelope_sent: bool = False
    completion_authorized: bool = False


def _canonical_uuid(value):
    try:
        normalized = str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Canonical UUID required.") from None

    if str(value) != normalized:
        raise ValidationError("Canonical UUID required.")
    return normalized


def require_completion_send_preflight(*, actor, attempt):
    """Fail-closed, read-only authorization for a future send service."""
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            not in (Role.SALES_MANAGER, Role.CEO)
    ):
        raise PermissionDenied(
            "Only an active Sales Manager or CEO may authorize sending."
        )

    if attempt is None:
        raise ValidationError("Completion attempt required.")

    package = getattr(attempt, "release_package", None)
    plan = getattr(package, "plan", None)
    msr = getattr(plan, "msr", None)
    project = getattr(msr, "project", None)

    if None in (package, plan, msr, project):
        raise ValidationError("Complete project/release binding required.")

    if (
        getattr(attempt, "release_package_id", None)
            != getattr(package, "pk", None)
        or getattr(plan, "msr_id", None) != getattr(msr, "pk", None)
        or getattr(msr, "project_id", None) != getattr(project, "pk", None)
        or getattr(project, "current_approved_id", None)
            != getattr(msr, "pk", None)
        or getattr(msr, "status", None) != "APPROVED"
        or getattr(project, "state", None) == "CANCELLED"
        or not isinstance(getattr(msr, "snapshot", None), dict)
    ):
        raise ValidationError(
            "Current approved project/MSR/release binding required."
        )

    group = getattr(plan, "group", None)
    financing = msr.snapshot.get("financing_type")
    if (
        group not in (
            "COMPLETION_FINANCED",
            "COMPLETION_NON_FINANCED",
        )
        or group != "COMPLETION_" + str(financing)
    ):
        raise ValidationError("Completion certificate group mismatch.")

    if (
        getattr(attempt, "state", None) != "AUTH_PENDING"
        or getattr(attempt, "provider_envelope_id", None) != ""
        or getattr(attempt, "first_send_started_at", None) is not None
    ):
        raise ValidationError(
            "Attempt is not eligible for its first authorized send."
        )

    _canonical_uuid(getattr(attempt, "provider_account_id", None))

    initiator = getattr(attempt, "initiated_by", None)
    if (
        initiator is None
        or not getattr(initiator, "is_active", False)
        or getattr(initiator, "role", None) != Role.COMPTROLLER
    ):
        raise ValidationError(
            "An active Comptroller-created attempt is required."
        )

    if getattr(initiator, "pk", None) == getattr(actor, "pk", None):
        raise PermissionDenied("Independent send authorization required.")

    from . import release

    release.validate_package(package, check_current=True)

    if release.status(package).get("status") != "APPROVED":
        raise ValidationError("Current release approval is required.")

    return CompletionSendPreflight(
        attempt_id=str(attempt.pk),
        project_id=str(project.pk),
        release_package_id=str(package.pk),
        actor_id=str(actor.pk),
        authority_validated=True,
        release_validated=True,
    )
