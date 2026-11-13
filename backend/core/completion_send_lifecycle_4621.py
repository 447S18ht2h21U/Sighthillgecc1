"""Fail-closed DocuSign send lifecycle decisions.

Policy only. Does not update models, alter triggers, call DocuSign,
or authorize live sending.

A network attempt must be durably recorded before a provider call.
An uncertain response must never trigger an automatic resend.
"""
from dataclasses import dataclass
from uuid import UUID

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .completion_send_authorization_4620 import ACTION


@dataclass(frozen=True)
class SendLifecycleDecision:
    attempt_id: str
    next_state: str
    provider_envelope_id: str
    first_send_required: bool
    retry_allowed: bool = False
    network_request_permitted: bool = False
    completion_authorized: bool = False


def canonical_uuid(value):
    if not isinstance(value, str):
        raise ValidationError("Provider envelope UUID required.")
    try:
        normalized = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Provider envelope UUID invalid.") from None
    if value != normalized:
        raise ValidationError("Provider envelope UUID must be canonical.")
    return normalized


def require_send_start_decision(
    *, actor, attempt, authorization_event, manifest
):
    """Validate a durable send-intent prerequisite, without sending."""
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

    if attempt is None or authorization_event is None:
        raise ValidationError("Bound attempt and authorization required.")

    package = getattr(attempt, "release_package", None)
    plan = getattr(package, "plan", None)
    msr = getattr(plan, "msr", None)
    project = getattr(msr, "project", None)
    payload = getattr(authorization_event, "payload", None)

    if (
        package is None
        or plan is None
        or msr is None
        or project is None
        or not isinstance(payload, dict)
    ):
        raise ValidationError("Authorization evidence binding missing.")

    if (
        getattr(attempt, "state", None) != "AUTH_PENDING"
        or getattr(attempt, "first_send_started_at", None) is not None
        or getattr(attempt, "provider_envelope_id", None) != ""
        or getattr(project, "current_approved_id", None)
            != getattr(msr, "pk", None)
        or getattr(msr, "status", None) != "APPROVED"
        or getattr(project, "state", None) == "CANCELLED"
        or getattr(plan, "group", None) not in (
            "COMPLETION_FINANCED",
            "COMPLETION_NON_FINANCED",
        )
    ):
        raise ValidationError("Attempt is not eligible for first send.")

    account = canonical_uuid(
        getattr(attempt, "provider_account_id", None)
    )

    expected = {
        "attempt_id": str(attempt.pk),
        "project_id": str(project.pk),
        "approved_msr_id": str(msr.pk),
        "release_package_id": str(package.pk),
        "release_package_digest": package.digest,
        "provider_account_id": account,
        "authorizing_actor_id": str(actor.pk),
        "initiating_comptroller_id": str(attempt.initiated_by_id),
        "certificate_group": plan.group,
        "attempt_state": "AUTH_PENDING",
        "provider_envelope_id": "",
        "live_send_authorized": False,
        "email_sent": False,
        "provider_authenticated": False,
        "completion_authorized": False,
        "signature_tabs_checked": True,
        "signed_date_tabs_checked": True,
    }

    if (
        authorization_event.action != ACTION
        or str(authorization_event.actor_id) != str(actor.pk)
        or str(authorization_event.entity_id) != str(project.pk)
        or any(payload.get(key) != value
               for key, value in expected.items())
        or payload.get("document_sha256")
            != list(getattr(manifest, "document_sha256", ()))
        or payload.get("recipient_ids")
            != list(getattr(manifest, "recipient_ids", ()))
        or getattr(manifest, "attempt_id", None) != str(attempt.pk)
        or getattr(manifest, "project_id", None) != str(project.pk)
        or getattr(manifest, "release_package_id", None)
            != str(package.pk)
        or not getattr(manifest, "signature_tabs_checked", False)
        or not getattr(manifest, "signed_date_tabs_checked", False)
        or getattr(manifest, "ready_for_live_send", True)
        or getattr(manifest, "envelope_sent", True)
        or getattr(manifest, "completion_authorized", True)
    ):
        raise ValidationError(
            "Audited sending authorization or manifest binding changed."
        )

    return SendLifecycleDecision(
        attempt_id=str(attempt.pk),
        next_state="NETWORK_STARTED",
        provider_envelope_id="",
        first_send_required=True,
    )


def require_provider_outcome_decision(
    *, attempt, outcome, provider_envelope_id=None
):
    """Interpret one provider response after a durable network-start record.

    The caller must separately prove the response came from its
    authenticated provider request. This function never makes that claim.
    """
    if (
        attempt is None
        or getattr(attempt, "state", None) != "NETWORK_STARTED"
        or getattr(attempt, "first_send_started_at", None) is None
        or getattr(attempt, "provider_envelope_id", None) != ""
    ):
        raise ValidationError(
            "Provider results require an existing network-start record."
        )

    if outcome == "CONFIRMED":
        envelope = canonical_uuid(provider_envelope_id)
        state = "SENT_UNCHECKED"
    elif outcome == "UNCERTAIN":
        if provider_envelope_id not in (None, ""):
            raise ValidationError(
                "Uncertain results cannot claim a confirmed envelope ID."
            )
        envelope = ""
        state = "SEND_UNCERTAIN"
    else:
        raise ValidationError("Unsupported provider outcome.")

    return SendLifecycleDecision(
        attempt_id=str(attempt.pk),
        next_state=state,
        provider_envelope_id=envelope,
        first_send_required=False,
        retry_allowed=False,
        network_request_permitted=False,
        completion_authorized=False,
    )
