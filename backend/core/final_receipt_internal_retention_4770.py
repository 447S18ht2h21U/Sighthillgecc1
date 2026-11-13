"""Development-only immutable storage of INTERNAL V4 Receipt preparations.

Never marks a Receipt FINAL, issues a customer document, sends email,
trusts candidate equipment evidence, or authorizes completion.
No API route is registered for this service.
"""

import hashlib
import os
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .approved_final_receipt_reference_4756 import (
    verify_approved_final_receipt,
)
from .documents import canonical_hash
from .final_receipt_financial_evidence_4760 import (
    assess_final_receipt_finances,
)
from .final_receipt_renderer_4762 import render_v4_receipt_internal
from .models import Document, Project, Role, User
from .services import audit


RENDERER_VERSION = "V4I4770"
INTERNAL_STATUS = "PREPARATION"
MAX_BYTES = 5 * 1024 * 1024


def validate_internal_receipt_document(
    document, *, msr, reference_sha256, snapshot_sha256
):
    """Reject damaged, replaced, or incorrectly classified stored bytes."""
    if (
        document.msr_id != msr.pk
        or document.kind != Document.Kind.RECEIPT
        or document.status != INTERNAL_STATUS
        or document.template_sha256 != reference_sha256
        or document.snapshot_sha256 != snapshot_sha256
        or document.renderer_version != RENDERER_VERSION
    ):
        raise ValidationError("Stored Receipt preparation identity differs.")

    try:
        content = bytes(document.content)
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Stored Receipt bytes are invalid.") from None

    # Always parse the actual PDF. A matching hash and embedded
    # watermark bytes alone do not establish a valid document.
    from io import BytesIO
    from pypdf import PdfReader

    if (
        len(content) < 8
        or len(content) > MAX_BYTES
        or not content.startswith(b"%PDF-")
        or hashlib.sha256(content).hexdigest() != document.pdf_sha256
    ):
        raise ValidationError("Stored Receipt fingerprint differs.")

    try:
        reader = PdfReader(BytesIO(content), strict=True)

        if reader.is_encrypted or len(reader.pages) != 1:
            raise ValueError("Invalid PDF structure.")

        page = reader.pages[0]

        if (
            float(page.mediabox.width),
            float(page.mediabox.height),
        ) != (792.0, 612.0):
            raise ValueError("Invalid approved Receipt geometry.")

        visible = page.extract_text() or ""

    except Exception:
        raise ValidationError(
            "Stored Receipt PDF cannot be verified."
        ) from None

    if "INTERNAL - NOT ISSUED" not in visible:
        raise ValidationError(
            "Internal-use marking is missing from rendered PDF."
        )

    values = document.values
    if (
        type(values) is not dict
        or values.get("purpose") != "INTERNAL_NOT_ISSUED"
        or values.get("msr_id") != str(msr.pk)
        or values.get("msr_version") != msr.number
        or values.get("customer_delivery_verified") is not False
        or values.get("completion_authorized") is not False
    ):
        raise ValidationError("Stored Receipt preparation metadata differs.")

    return True


@transaction.atomic
def retain_internal_v4_receipt(*, actor, project_id):
    """Store one versioned internal Receipt preparation, never a final one.

    This method is disabled unless explicitly enabled in isolated
    development. It must not be exposed as a live customer endpoint.
    """
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(
            "GECC_INTERNAL_RECEIPT_RETENTION_ENABLED", ""
        ) != "1"
    ):
        raise PermissionDenied("Internal Receipt retention is disabled.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated Comptroller required.")

    reviewer = User.objects.filter(pk=actor.pk).first()

    if (
        reviewer is None
        or reviewer.is_active is not True
        or reviewer.role != Role.COMPTROLLER
    ):
        raise PermissionDenied("Active Comptroller required.")

    project = Project.objects.select_for_update().select_related(
        "current_approved"
    ).filter(pk=project_id).first()

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or type(msr.snapshot) is not dict
    ):
        raise ValidationError("Current approved MSR required.")

    if (
        type(project.code) is not str
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", project.code)
    ):
        raise ValidationError("Safe project code required.")

    finances = assess_final_receipt_finances(project)

    if (
        finances.project_id != str(project.pk)
        or finances.approved_msr_id != str(msr.pk)
        or finances.approved_msr_version != msr.number
        or finances.overpayment_requires_review
    ):
        raise ValidationError("Financial evidence binding failed.")

    source = verify_approved_final_receipt()
    snapshot_digest = canonical_hash(msr.snapshot)

    identity = {
        "msr": msr,
        "kind": Document.Kind.RECEIPT,
        "template_sha256": source.sha256,
        "renderer_version": RENDERER_VERSION,
    }

    existing = Document.objects.filter(**identity).first()

    if existing is not None:
        validate_internal_receipt_document(
            existing,
            msr=msr,
            reference_sha256=source.sha256,
            snapshot_sha256=snapshot_digest,
        )
        return existing, False

    issued_on = timezone.localdate()
    internal_number = f"{project.code}-V{msr.number}-INTERNAL"

    rendered = render_v4_receipt_internal(
        snapshot=msr.snapshot,
        project_id=str(project.pk),
        approved_msr_id=str(msr.pk),
        project_code=project.code,
        invoice_number=internal_number,
        invoice_date=issued_on,
        finances=finances,
    )

    if (
        rendered.status != "INTERNAL_NOT_ISSUED"
        or rendered.project_id != str(project.pk)
        or rendered.approved_msr_id != str(msr.pk)
        or rendered.reference_sha256 != source.sha256
        or len(rendered.content) < 8
        or len(rendered.content) > MAX_BYTES
        or hashlib.sha256(rendered.content).hexdigest()
            != rendered.pdf_sha256
    ):
        raise ValidationError("Internal V4 rendering integrity failed.")

    values = {
        "purpose": "INTERNAL_NOT_ISSUED",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "reference_sha256": source.sha256,
        "verified_customer_funds": str(
            finances.verified_customer_funds
        ),
        "outstanding_balance": str(finances.outstanding_balance),
        "created_on": issued_on.isoformat(),
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }

    document = Document.objects.create(
        **identity,
        created_by=reviewer,
        status=INTERNAL_STATUS,
        filename=(
            f"{project.code}-V{msr.number}-"
            "RECEIPT-INTERNAL-NOT-ISSUED.pdf"
        ),
        snapshot_sha256=snapshot_digest,
        pdf_sha256=rendered.pdf_sha256,
        values=values,
        content=rendered.content,
    )

    validate_internal_receipt_document(
        document,
        msr=msr,
        reference_sha256=source.sha256,
        snapshot_sha256=snapshot_digest,
    )

    audit(
        reviewer,
        "receipt.internal_preparation_retained",
        project.pk,
        {
            "document_id": str(document.pk),
            "msr_id": str(msr.pk),
            "pdf_sha256": document.pdf_sha256,
            "final_receipt_verified": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        },
    )

    return document, True
