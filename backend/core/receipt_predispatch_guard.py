"""Fail-closed read-only gate before any future Receipt dispatch.

This does not send email, authorize completion, or authenticate a provider.
"""
import hashlib
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .models import Document, Project, Role, User


@dataclass(frozen=True)
class ReceiptPredispatchApproval:
    project_id: str
    msr_id: str
    document_id: str
    recipient: str
    pdf_sha256: str
    test_only: bool = True
    provider_authenticated: bool = False
    delivery_verified: bool = False
    completion_authorized: bool = False


def validate_receipt_before_dispatch(
    *, actor, project_id, document_id, recipient, pdf_bytes,
):
    """Inspect original database records before attempting email transport."""
    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated Comptroller required.")
    try:
        user = User.objects.get(pk=actor.pk)
    except User.DoesNotExist:
        raise PermissionDenied("Active Comptroller required.")
    if not user.is_active or user.role != Role.COMPTROLLER:
        raise PermissionDenied("Active Comptroller required.")

    project = Project.objects.select_related("current_approved").get(
        pk=project_id
    )
    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        raise ValidationError("Matching current approved MSR required.")

    if not isinstance(msr.snapshot, dict):
        raise ValidationError("Approved MSR snapshot missing.")
    approved_email = msr.snapshot.get("customer_email")
    if (
        not isinstance(approved_email, str)
        or not approved_email.strip()
        or not isinstance(recipient, str)
        or recipient.strip().casefold() != approved_email.strip().casefold()
    ):
        raise ValidationError("Recipient differs from approved MSR.")

    document = Document.objects.get(
        pk=document_id, msr=msr, kind=Document.Kind.INVOICE
    )
    if document.status != "PREPARATION":
        raise ValidationError("Document not eligible for test dispatch.")
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise ValidationError("Receipt PDF required.")
    stored = bytes(document.content)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if (
        stored != pdf_bytes
        or not stored.startswith(b"%PDF-")
        or digest != document.pdf_sha256.lower()
    ):
        raise ValidationError("Exact retained PDF fingerprint required.")

    return ReceiptPredispatchApproval(
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        document_id=str(document.pk),
        recipient=recipient.strip(),
        pdf_sha256=digest,
    )