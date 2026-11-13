"""Authenticated completion provider handoff, with no network I/O.

Requires a verified sender OAuth proof bound to the exact attempt,
session challenge, sandbox account, and current approved release.
Returns only request metadata. Does not expose a bearer token or PDF.
"""
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign
from .completion_provider_payload_4626 import (
    build_completion_envelope,
)
from .completion_send_oauth_4627 import _isolated
from .documents import canonical_hash
from .models import (
    CompletionEnvelopeAttempt, DocusignVerification, Project, Role,
)


@transaction.atomic
def prepare_verified_handoff(*, actor, attempt_id, verification_id):
    """Validate a sender identity and prepare a draft without sending."""
    _isolated()

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None)
            not in (Role.SALES_MANAGER, Role.CEO)
    ):
        raise PermissionDenied("Unauthorized completion sender.")

    reference = CompletionEnvelopeAttempt.objects.select_related(
        "release_package__plan__msr"
    ).get(pk=attempt_id)

    project_id = reference.release_package.plan.msr.project_id
    Project.objects.select_for_update().get(pk=project_id)

    attempt = CompletionEnvelopeAttempt.objects.select_for_update().select_related(
        "release_package__plan__msr__project"
    ).get(pk=attempt_id)

    proof = DocusignVerification.objects.select_related(
        "challenge"
    ).get(pk=verification_id)

    identity = proof.identity
    challenge = proof.challenge
    context = challenge.context

    if (
        not isinstance(identity, dict)
        or not isinstance(context, dict)
        or canonical_hash(identity) != proof.digest
        or proof.actor_id != actor.pk
        or challenge.actor_id != actor.pk
        or challenge.consumed_at is None
        or context.get("operation") != "SANDBOX_COMPLETION_SEND"
        or context.get("send_enabled") is not False
        or identity.get("purpose")
            != "SANDBOX_COMPLETION_SENDER_IDENTITY_ONLY"
        or identity.get("environment") != "SANDBOX"
        or identity.get("tokens_retained") is not False
        or identity.get("send_enabled") is not False
        or identity.get("envelope_sent") is not False
        or identity.get("completion_attempt_id")
            != str(attempt.pk)
        or identity.get("authorization_challenge_id")
            != str(challenge.pk)
        or context.get("completion_attempt_id")
            != str(attempt.pk)
        or context.get("project_id") != str(project_id)
        or context.get("release_package_id")
            != str(attempt.release_package_id)
        or context.get("release_package_digest")
            != attempt.release_package.digest
        or context.get("authorizing_actor_id")
            != str(actor.pk)
        or context.get("account_id")
            != attempt.provider_account_id
        or identity.get("account_id")
            != attempt.provider_account_id
        or attempt.state != "AUTH_PENDING"
        or attempt.first_send_started_at is not None
        or attempt.provider_envelope_id != ""
    ):
        raise ValidationError(
            "Sender OAuth verification is not valid for this attempt."
        )

    config = docusign.configuration()

    if (
        config["blockers"]
        or config["account_id"] != attempt.provider_account_id
        or config["client_id"] != identity.get("client_id")
        or challenge.configuration_digest
            != docusign.configuration_digest(config)
    ):
        raise ValidationError(
            "Sender OAuth configuration or account changed."
        )

    prepared = build_completion_envelope(
        actor=actor,
        attempt=attempt,
    )

    recipients = (
        prepared.payload.get("recipients", {})
        if isinstance(prepared.payload, dict)
        else {}
    )
    signers = (
        recipients.get("signers", [])
        if isinstance(recipients, dict)
        else []
    )
    recipient_ids = (
        [signer.get("recipientId") for signer in signers]
        if isinstance(signers, list)
        and all(isinstance(signer, dict) for signer in signers)
        else []
    )

    if (
        not recipient_ids
        or any(
            not isinstance(value, str) or not value
            for value in recipient_ids
        )
        or len(set(recipient_ids)) != len(recipient_ids)
        or context.get("recipient_ids") != recipient_ids
        or prepared.attempt_id != str(attempt.pk)
        or prepared.account_id != attempt.provider_account_id
        or prepared.send_available
        or prepared.envelope_sent
        or prepared.provider_authenticated
        or context.get("document_sha256")
            != list(prepared.document_sha256)
    ):
        raise ValidationError(
            "Prepared completion certificate is not bound to OAuth."
        )

    # Do not produce a bearer token or create a provider request.
    # No provider-side draft or sent envelope is implied.
    return {
        "attempt_id": str(attempt.pk),
        "verification_id": str(proof.pk),
        "provider_account_id": attempt.provider_account_id,
        "document_sha256": list(prepared.document_sha256),
        "oauth_identity_verified": True,
        "request_prepared_locally": True,
        "provider_request_executed": False,
        "envelope_sent": False,
        "completion_authorized": False,
        "retry_allowed": False,
    }
