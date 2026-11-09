"""Unregistered audited storage; never proves a Receipt was emailed."""
import hashlib
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Document, Project, ReceiptSendingObservation, Role, User
from .services import audit


@transaction.atomic
def record_unverified_receipt_observation(
    *, actor, project_id, document_id, recipient_email,
    provider_reference, observed_sent_at,
    observation_source="MANUAL_OBSERVATION",
):
    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated Comptroller required.")
    fresh_actor = User.objects.get(pk=actor.pk)
    if not fresh_actor.is_active or fresh_actor.role != Role.COMPTROLLER:
        raise PermissionDenied("Active Comptroller required.")

    project = Project.objects.select_for_update().get(pk=project_id)
    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        raise ValidationError("Matching current approved MSR required.")

    document = Document.objects.get(
        pk=document_id, msr=msr, kind=Document.Kind.INVOICE
    )
    if document.status != "PREPARATION":
        raise ValidationError("Unexpected historical document status.")

    expected_email = msr.snapshot.get("customer_email")
    if (
        not isinstance(expected_email, str)
        or not expected_email.strip()
        or not isinstance(recipient_email, str)
        or not recipient_email.strip()
        or expected_email.strip().casefold() != recipient_email.strip().casefold()
    ):
        raise ValidationError("Email recipient must match the approved MSR.")

    content = bytes(document.content)
    fingerprint = hashlib.sha256(content).hexdigest()
    if not content.startswith(b"%PDF-") or fingerprint != document.pdf_sha256.lower():
        raise ValidationError("Retained PDF fingerprint mismatch.")
    if (
        observed_sent_at is None
        or timezone.is_naive(observed_sent_at)
        or observed_sent_at > timezone.now()
    ):
        raise ValidationError("Invalid observation timestamp.")

    observation = ReceiptSendingObservation.objects.create(
        msr=msr, document=document, recorded_by=fresh_actor,
        recipient_email=recipient_email,
        provider_reference=provider_reference,
        sent_at=observed_sent_at, pdf_sha256=fingerprint,
        observation_source=observation_source, status="UNVERIFIED",
    )

    audit(
        fresh_actor, "receipt.unverified_observation_recorded",
        project.pk, {
            "observation_id": str(observation.pk),
            "msr_id": str(msr.pk),
            "document_id": str(document.pk),
            "pdf_sha256": fingerprint,
            "status": "UNVERIFIED",
            "provider_authenticated": False,
            "receipt_sent_verified": False,
            "completion_authorized": False,
        },
    )
    return observation