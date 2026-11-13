"""OAuth-bound DocuSign completion read; sandbox only, no sending."""
import os
from uuid import UUID

from django.db import transaction
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign, release
from .models import CompletionEnvelopeAttempt, Role
from .completion_provider_read_4610 import read_completed_certificate

OPERATION = "SANDBOX_COMPLETION_READ"


def _uuid(value):
    try:
        result = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Canonical identifier required.") from None
    if result != str(value):
        raise ValidationError("Canonical identifier required.")
    return result


def _active_comptroller(actor):
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied("An active Comptroller is required.")


def _eligible_attempt(actor, attempt_id):
    _active_comptroller(actor)

    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError("Sandbox completion verification is development-only.")

    attempt = (
        CompletionEnvelopeAttempt.objects
        .select_related("release_package__plan__msr__project")
        .get(pk=_uuid(attempt_id))
    )
    package = attempt.release_package
    project = package.plan.msr.project

    if (
        project.state == "CANCELLED"
        or project.current_approved_id != package.plan.msr_id
        or package.plan.group not in (
            "COMPLETION_FINANCED",
            "COMPLETION_NON_FINANCED",
        )
        or package.plan.group != (
            "COMPLETION_" +
            str(package.plan.msr.snapshot.get("financing_type", ""))
        )
    ):
        raise ValidationError("Current completion release binding is invalid.")

    release.validate_package(package, check_current=True)

    if release.status(package).get("status") != "APPROVED":
        raise ValidationError("An approved current release is required.")

    account = _uuid(attempt.provider_account_id)
    envelope = _uuid(attempt.provider_envelope_id)

    if (
        attempt.state != "SENT_UNCHECKED"
        or attempt.first_send_started_at is None
    ):
        raise ValidationError(
            "A previously sent, identified envelope is required. "
            "No sending is available from this operation."
        )

    preview = package.plan.review.get("envelope_preview")
    if (
        not isinstance(preview, dict)
        or not isinstance(preview.get("documents"), list)
        or not isinstance(preview.get("recipients"), dict)
    ):
        raise ValidationError("Approved immutable signing preview is missing.")

    return attempt, account, envelope, preview


@transaction.atomic
def begin(actor, session_key, attempt_id):
    attempt, account, envelope, preview = _eligible_attempt(
        actor, attempt_id
    )
    config = docusign.configuration()

    if config["blockers"] or config["account_id"] != account:
        raise ValidationError("Configured sandbox account does not match.")

    context = {
        "operation": OPERATION,
        "completion_attempt_id": str(attempt.pk),
        "release_package_id": str(attempt.release_package_id),
        "release_package_digest": attempt.release_package.digest,
        "project_id": str(attempt.release_package.plan.msr.project_id),
        "msr_id": str(attempt.release_package.plan.msr_id),
        "account_id": account,
        "envelope_id": envelope,
    }

    result = docusign.begin(actor, session_key, context)

    return {
        "authorization_url": result["authorization_url"],
        "expires_at": result["expires_at"],
        "environment": "SANDBOX",
        "purpose": "COMPLETION_READ_ONLY",
        "send_available": False,
        "completion_authorized": False,
    }


def finish(actor, challenge, config, token):
    _active_comptroller(actor)
    context = challenge.context

    if (
        not isinstance(context, dict)
        or context.get("operation") != OPERATION
        or challenge.actor_id != actor.pk
    ):
        raise PermissionDenied("Completion authorization context mismatch.")

    attempt_id = _uuid(context.get("completion_attempt_id"))

    attempt, account, envelope, preview = _eligible_attempt(
        actor, attempt_id
    )

    expected_context = {
        "release_package_id": str(attempt.release_package_id),
        "release_package_digest": attempt.release_package.digest,
        "project_id": str(attempt.release_package.plan.msr.project_id),
        "msr_id": str(attempt.release_package.plan.msr_id),
        "account_id": account,
        "envelope_id": envelope,
    }

    if any(context.get(key) != value
           for key, value in expected_context.items()):
        raise ValidationError("Completion OAuth context changed.")

    if config.get("account_id") != account:
        raise ValidationError("OAuth account does not match the envelope.")

    evidence = read_completed_certificate(
        account_id=account,
        envelope_id=envelope,
        token=token,
        expected=preview,
        retain_bytes=True,
    )

    if (
        evidence.get("provider_response_validated") is not True
        or evidence.get("completion_authorized") is not False
        or evidence.get("project_completed") is not False
    ):
        raise ValidationError("Unexpected provider verification authority.")

    retained = False

    if os.environ.get(
        "GECC_SANDBOX_COMPLETION_RETENTION_ENABLED", ""
    ) == "1":
        from .completion_retention_4612 import (
            retain_authenticated_completion,
        )
        retain_authenticated_completion(
            actor=actor,
            attempt_id=str(attempt.pk),
            challenge=challenge,
            evidence=evidence,
        )
        retained = True

    # Never expose PDF bytes, provider credentials or OAuth codes.
    evidence.pop("_validated_pdf_bytes", None)

    return {
        "status": (
            "SANDBOX_COMPLETION_EVIDENCE_RETAINED"
            if retained
            else "SANDBOX_COMPLETION_PROVIDER_READ_VALIDATED"
        ),
        "project_id": expected_context["project_id"],
        "msr_id": expected_context["msr_id"],
        "attempt_id": str(attempt.pk),
        "provider_response_validated": True,
        "completed_at": evidence["completed_at"],
        "pdf_manifest": evidence["pdf_manifest"],
        "oauth_callback_binding_verified": True,
        "signed_documents_retained": retained,
        "receipt_email_authenticated": False,
        "completion_authorized": False,
        "project_completed": False,
        "message": (
            "Sandbox provider response processed. Certificate retention "
            "does not authenticate Receipt email evidence or authorize "
            "project completion."
        ),
    }
