"""Audited Receipt outbox request creation; NO email dispatch.

A committed PENDING record is an intent, never authenticated delivery.
Operational routes and provider sending remain disabled.
"""
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Project, ReceiptDispatchOutbox
from .receipt_predispatch_guard import validate_receipt_before_dispatch
from .services import audit


@transaction.atomic
def request_receipt_outbox(
    *, actor, project_id, document_id, recipient, pdf_bytes,
    idempotency_key,
):
    """Authorize, lock the project, store an intent, then audit atomically."""
    if not isinstance(idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{8,128}", idempotency_key
    ):
        raise ValidationError("Invalid Receipt request key.")

    project = Project.objects.select_for_update().get(pk=project_id)

    approval = validate_receipt_before_dispatch(
        actor=actor, project_id=project.pk,
        document_id=document_id, recipient=recipient,
        pdf_bytes=pdf_bytes,
    )
    if (
        not approval.test_only
        or approval.provider_authenticated
        or approval.delivery_verified
        or approval.completion_authorized
        or approval.project_id != str(project.pk)
        or approval.document_id != str(document_id)
    ):
        raise ValidationError("Receipt authorization binding is invalid.")

    # Duplicate requests must not create a second outbox entry.
    # The database unique constraint also protects against races.
    if ReceiptDispatchOutbox.objects.filter(
        project=project, idempotency_key=idempotency_key
    ).exists():
        raise ValidationError("Receipt request key already used.")

    entry = ReceiptDispatchOutbox.objects.create(
        project=project,
        msr_id=approval.msr_id,
        document_id=approval.document_id,
        requested_by=actor,
        idempotency_key=idempotency_key,
        recipient_email=approval.recipient,
        pdf_sha256=approval.pdf_sha256,
        status="PENDING",
    )
    audit(
        actor, "receipt.outbox_intent_created", project.pk,
        {
            "outbox_id": str(entry.pk),
            "msr_id": str(entry.msr_id),
            "document_id": str(entry.document_id),
            "idempotency_key": entry.idempotency_key,
            "pdf_sha256": entry.pdf_sha256,
            "status": "PENDING",
            "email_sent": False,
            "provider_authenticated": False,
            "completion_authorized": False,
        },
    )
    return entry