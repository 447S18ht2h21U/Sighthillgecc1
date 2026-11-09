"""Unregistered VERIDIAN Invoice observation prototype.

Development-only. Records untrusted synthetic observations.
Never sends, verifies delivery, or changes installation eligibility.
"""
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .invoice_delivery_binding import verify_candidate_binding
from .invoice_delivery_evidence import assess_delivery_candidate, preflight_provider_observation
from .models import Document, Project, ProjectEvidence, Role, User
from .services import audit


KIND = "INVOICE_DELIVERY_OBSERVATION"


@transaction.atomic
def record_synthetic_invoice_observation(
    actor, project_id, document_id, candidate_data, provider_observation,
    *, expected_account_id, expected_envelope_id,
    expected_provider_document_id, expected_recipient_id,
):
    """Persist only untrusted, version-bound synthetic evidence."""
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError("Synthetic observation recording is development-only.")
    if not isinstance(candidate_data, dict):
        raise ValidationError("Candidate evidence must be an object.")

    project = Project.objects.select_for_update().get(pk=project_id)
    fresh_actor = User.objects.get(pk=actor.pk)
    if not fresh_actor.is_active or fresh_actor.role != Role.COMPTROLLER:
        raise PermissionDenied("Only an active Comptroller may record this prototype evidence.")

    msr = project.current_approved
    if project.state == "CANCELLED" or msr is None or msr.status != "APPROVED":
        raise ValidationError("A current approved MSR on an active project is required.")

    document = Document.objects.get(pk=document_id, msr=msr, kind="INVOICE")
    if document.status != "PREPARATION":
        raise ValidationError("Unexpected Invoice document status.")

    candidate = assess_delivery_candidate(**candidate_data)
    binding = verify_candidate_binding(
        candidate,
        current_approved_msr_id=str(msr.pk),
        expected_document_id=str(document.pk),
        expected_pdf_sha256=document.pdf_sha256,
        expected_recipient_email=msr.snapshot.get("customer_email"),
        expected_document_kind=document.kind,
        document_status=document.status,
        document_msr_id=str(document.msr_id),
    )
    if not binding.candidate_matches:
        raise ValidationError("Observation is not bound to the current approved Invoice.")

    if not preflight_provider_observation(
        provider_observation,
        expected_account_id=expected_account_id,
        expected_envelope_id=expected_envelope_id,
        expected_document_id=expected_provider_document_id,
        expected_recipient_id=expected_recipient_id,
        expected_recipient_email=msr.snapshot.get("customer_email"),
    ):
        raise ValidationError("Provider-shaped observation does not match expected values.")

    # These references are test inputs only, never authenticated provider proof.
    payload = {
        "purpose": "SYNTHETIC_UNTRUSTED_INVOICE_OBSERVATION",
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "document_id": str(document.pk),
        "invoice_sha256": document.pdf_sha256,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "recipient_email": msr.snapshot["customer_email"],
        "claimed_channel": candidate.channel,
        "claimed_provider_reference": candidate.provider_reference,
        "claimed_delivery_at": candidate.delivered_at.isoformat(),
        "observed_status": provider_observation["status"],
        "verified": False,
        "trusted_delivery": False,
        "installation_evidence_accepted": False,
        "source_authenticity": "NOT_VERIFIED",
    }

    digest = canonical_hash(payload)
    existing = ProjectEvidence.objects.filter(
        msr=msr, kind=KIND, digest=digest
    ).first()
    if existing:
        return existing, False

    evidence = ProjectEvidence.objects.create(
        msr=msr, kind=KIND, created_by=fresh_actor,
        data=payload, digest=digest,
    )
    audit(
        fresh_actor,
        "invoice.delivery_observation_recorded",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "msr_id": str(msr.pk),
            "document_id": str(document.pk),
            "digest": digest,
            "trusted_delivery": False,
        },
    )
    return evidence, True