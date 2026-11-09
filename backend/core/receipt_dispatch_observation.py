"""Unregistered test dispatch followed by an UNVERIFIED observation."""
from django.core.exceptions import ValidationError
from django.db import transaction

from .receipt_provider_dispatch import dispatch_receipt
from .receipt_observation_recording import (
    record_unverified_receipt_observation,
)


@transaction.atomic
def dispatch_and_observe_test_receipt(
    *, actor, project_id, document_id, pdf_bytes,
    expected_sha256, recipient, approved_email,
    observed_sent_at, connection, provider_reference,
):
    """Test backend only. Never grants provider trust or completion."""
    if (
        not isinstance(provider_reference, str)
        or not provider_reference.startswith("TEST-")
        or len(provider_reference) > 256
    ):
        raise ValidationError("Test-only reference required.")

    # Sequential, test-only duplicate guard.
    # Production must add a durable unique key and concurrency controls.
    from .models import ReceiptSendingObservation

    if ReceiptSendingObservation.objects.filter(
        msr__project_id=project_id,
        document_id=document_id,
        provider_reference=provider_reference,
    ).exists():
        raise ValidationError(
            "Duplicate test reference: existing observation requires review."
        )
    decision = dispatch_receipt(
        pdf_bytes=pdf_bytes,
        expected_sha256=expected_sha256,
        recipient=recipient,
        approved_email=approved_email,
        connection=connection,
        mode="TEST_MEMORY",
    )
    if (
        not decision.test_submission
        or decision.provider_authenticated
        or decision.customer_delivery_verified
        or decision.completion_authorized
    ):
        raise ValidationError("Unexpected dispatch trust status.")

    observation = record_unverified_receipt_observation(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
        recipient_email=decision.recipient,
        provider_reference=provider_reference,
        observed_sent_at=observed_sent_at,
        observation_source="MANUAL_OBSERVATION",
    )
    if observation.status != "UNVERIFIED":
        raise ValidationError("Unverified status is mandatory.")
    return observation