"""Unregistered, secure test-only Receipt workflow.

Authorize and check persisted PDF BEFORE any test email submission.
This service cannot send a real email or verify customer delivery.
"""
from django.core.exceptions import ValidationError
from django.core.mail.backends.locmem import EmailBackend as MemoryBackend

from .receipt_predispatch_guard import validate_receipt_before_dispatch
from .receipt_dispatch_observation import (
    dispatch_and_observe_test_receipt,
)


def secure_test_receipt_dispatch(
    *, actor, project_id, document_id, recipient, pdf_bytes,
    observed_sent_at, connection, provider_reference,
):
    """Fail closed before dispatch and retain only unverified claims."""
    if connection is None or type(connection) is not MemoryBackend:
        raise ValidationError("Explicit test-only email backend required.")

    approval = validate_receipt_before_dispatch(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
        recipient=recipient,
        pdf_bytes=pdf_bytes,
    )

    if (
        not approval.test_only
        or approval.provider_authenticated
        or approval.delivery_verified
        or approval.completion_authorized
    ):
        raise ValidationError("Unexpected authorization trust flags.")

    if (
        approval.project_id != str(project_id)
        or approval.document_id != str(document_id)
        or approval.recipient.casefold() != recipient.strip().casefold()
    ):
        raise ValidationError("Authorization binding mismatch.")

    observation = dispatch_and_observe_test_receipt(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
        pdf_bytes=pdf_bytes,
        expected_sha256=approval.pdf_sha256,
        recipient=approval.recipient,
        approved_email=approval.recipient,
        observed_sent_at=observed_sent_at,
        connection=connection,
        provider_reference=provider_reference,
    )

    if observation.status != "UNVERIFIED":
        raise ValidationError("A test observation cannot grant delivery trust.")

    return observation