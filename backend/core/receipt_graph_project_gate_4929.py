"""Database-bound, fail-closed Microsoft Graph Receipt preview.

No email transport, document creation, issuance authority, or delivery trust.
"""

import hashlib

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .models import Document, Project, Role, User
from .final_receipt_issuance_boundary_4781 import (
    assess_final_receipt_issuance_boundary,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)
from .receipt_microsoft_graph_preview_4927 import (
    prepare_graph_receipt_preview,
)


def prepare_project_graph_receipt_preview(
    *, actor, project_id, document_id
):
    """Read persisted records and refuse Graph preparation until issuance is authorized."""
    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated Receipt reviewer required.")

    fresh = User.objects.filter(
        pk=actor.pk, is_active=True
    ).first()
    if fresh is None or fresh.role not in (
        Role.CEO, Role.COMPTROLLER
    ):
        raise PermissionDenied("CEO or Comptroller review required.")

    project = Project.objects.select_related(
        "current_approved"
    ).get(pk=project_id)

    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or not isinstance(msr.snapshot, dict)
    ):
        raise ValidationError("Current approved project/MSR required.")

    # A caller's 'FINAL' label is never sufficient. Both independent
    # issuance/readiness services must positively authorize the action.
    issuance = assess_final_receipt_issuance_boundary(project)
    release = assess_final_receipt_release_preflight(project)

    if (
        issuance.project_id != str(project.pk)
        or issuance.msr_id != str(msr.pk)
        or release.project_id != str(project.pk)
        or release.msr_id != str(msr.pk)
        or issuance.customer_receipt_issuance_authorized is not True
        or release.final_receipt_issuance_authorized is not True
        or issuance.trusted_installation_evidence is not True
        or release.trusted_installation_evidence is not True
    ):
        raise PermissionDenied(
            "FINAL Receipt issuance has not been independently authorized."
        )

    document = Document.objects.get(
        pk=document_id,
        msr=msr,
        kind=Document.Kind.RECEIPT,
    )

    if document.status != "FINAL":
        raise ValidationError("Issued FINAL Receipt required.")

    pdf = bytes(document.content)
    digest = hashlib.sha256(pdf).hexdigest()

    if digest != document.pdf_sha256.lower():
        raise ValidationError("Retained FINAL Receipt fingerprint mismatch.")

    recipient = msr.snapshot.get("customer_email")

    return prepare_graph_receipt_preview(
        pdf_bytes=pdf,
        expected_sha256=digest,
        recipient=recipient,
        approved_email=recipient,
        approved_msr_id=str(msr.pk),
        document_msr_id=str(document.msr_id),
        document_kind=document.kind,
        document_status=document.status,
        mode="PREVIEW_ONLY",
    )
