"""Development-only, audited completion send authorization record.

No provider calls, no sending, no envelope-state transition.
An audit record does not grant the right to execute a live send.
"""
import os

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .completion_send_preflight_4618 import (
    require_completion_send_preflight,
)
from .completion_send_manifest_4619 import (
    prepare_completion_send_manifest,
)
from .documents import canonical_hash
from .models import AuditEvent, CompletionEnvelopeAttempt, Project, Role
from .services import audit


ACTION = "completion_envelope.send_authorization_recorded"


@transaction.atomic
def record_send_authorization(*, actor, attempt_id):
    """Record one independently authorized, still-unsent send decision.

    This operation is intentionally not exposed through an API.
    It cannot enable or initiate an actual provider request.
    """
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            not in (Role.SALES_MANAGER, Role.CEO)
    ):
        raise PermissionDenied(
            "Only an active Sales Manager or CEO may record "
            "completion send authorization."
        )

    if (
        settings.ENVIRONMENT != "development"
        or not settings.DEBUG
        or os.getenv(
            "GECC_DEV_COMPLETION_SEND_AUTH_RECORD_ENABLED"
        ) != "1"
    ):
        raise ValidationError(
            "Completion send authorization recording is disabled."
        )

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

    gate = require_completion_send_preflight(
        actor=actor, attempt=attempt
    )

    manifest = prepare_completion_send_manifest(
        actor=actor, attempt=attempt
    )

    if (
        gate.attempt_id != str(attempt.pk)
        or gate.project_id != str(project_id)
        or gate.release_package_id
            != str(attempt.release_package_id)
        or not gate.authority_validated
        or not gate.release_validated
        or gate.live_sending_enabled
        or gate.provider_authenticated
        or gate.envelope_sent
        or gate.completion_authorized
        or manifest.attempt_id != gate.attempt_id
        or manifest.project_id != gate.project_id
        or manifest.release_package_id != gate.release_package_id
        or not manifest.signature_tabs_checked
        or not manifest.signed_date_tabs_checked
        or manifest.ready_for_live_send
        or manifest.provider_authenticated
        or manifest.envelope_sent
        or manifest.completion_authorized
        or not manifest.document_sha256
    ):
        raise ValidationError(
            "The verified send manifest and authorization do not match."
        )

    existing = AuditEvent.objects.filter(
        action=ACTION,
        entity_id=project_id,
        payload__attempt_id=str(attempt.pk),
    )

    if existing.exists():
        raise ValidationError(
            "A send authorization already exists for this attempt. "
            "Review it before taking further action."
        )

    if (
        attempt.state != "AUTH_PENDING"
        or attempt.provider_envelope_id != ""
        or attempt.first_send_started_at is not None
    ):
        raise ValidationError(
            "Send authorization requires an unsent, unchanged attempt."
        )

    payload = {
        "schema_version": 1,
        "attempt_id": str(attempt.pk),
        "project_id": str(project_id),
        "approved_msr_id": str(
            attempt.release_package.plan.msr_id
        ),
        "release_package_id": str(attempt.release_package_id),
        "release_package_digest": attempt.release_package.digest,
        "provider_account_id": attempt.provider_account_id,
        "authorizing_actor_id": str(actor.pk),
        "initiating_comptroller_id": str(attempt.initiated_by_id),
        "certificate_group": attempt.release_package.plan.group,
        "document_sha256": list(manifest.document_sha256),
        "recipient_ids": list(manifest.recipient_ids),
        "signature_tabs_checked": True,
        "signed_date_tabs_checked": True,
        "attempt_state": "AUTH_PENDING",
        "provider_envelope_id": "",
        "live_send_authorized": False,
        "email_sent": False,
        "provider_authenticated": False,
        "completion_authorized": False,
    }
    payload["manifest_binding_sha256"] = canonical_hash(payload)

    event = audit(
        actor,
        ACTION,
        project_id,
        payload,
    )

    return {
        "audit_event_id": str(event.pk),
        "attempt_id": str(attempt.pk),
        "manifest_binding_sha256": payload[
            "manifest_binding_sha256"
        ],
        "recorded": True,
        "send_available": False,
        "provider_authenticated": False,
        "completion_authorized": False,
    }
