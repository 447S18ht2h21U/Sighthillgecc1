"""Development-gated, durable preparation for an INTERNAL DocuSign attestation.

No signing attempt, envelope dispatch, provider authentication, or Receipt
issuance is performed. ProjectEvidence is used without schema changes.
"""

import os

from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .installation_attestation_binding_4936 import (
    prepare_installation_attestation,
)
from .models import Project, ProjectEvidence, Role, User
from .services import audit


KIND = "INSTALL_ATTEST_PREP_4939"
PURPOSE = "INTERNAL_INSTALLATION_INSPECTION_ATTESTATION"


def _development_gate():
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED"
        ) != "1"
    ):
        raise PermissionDenied("Attestation preparation recording is disabled.")


@transaction.atomic
def record_installation_attestation_preparation(*, actor, project_id):
    """Idempotently retain an offline source/signer binding and chained audit."""
    _development_gate()

    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated attestation preparer required.")

    preparer = User.objects.filter(
        pk=actor.pk, is_active=True
    ).first()
    if preparer is None or preparer.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        raise PermissionDenied("Authorized attestation preparer required.")

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )
    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active persisted project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or type(msr.snapshot) is not dict
    ):
        raise ValidationError("Current approved MSR required.")

    prepared = prepare_installation_attestation(
        actor=preparer, project_id=project.pk, mode="OFFLINE_ONLY"
    )

    if (
        prepared.project_id != str(project.pk)
        or prepared.approved_msr_id != str(msr.pk)
        or prepared.approved_msr_version != msr.number
        or prepared.prepared_by_user_id != str(preparer.pk)
        or prepared.provider != "DOCUSIGN"
        or prepared.status != "OFFLINE_ATTESTATION_BINDING_NOT_SENT"
        or prepared.provider_envelope_id is not None
        or prepared.provider_authenticated is not False
        or prepared.source_artifact_authenticated is not False
        or prepared.trusted_installation_evidence is not False
        or prepared.final_receipt_issuance_authorized is not False
        or prepared.customer_delivery_verified is not False
        or prepared.completion_authorized is not False
        or type(prepared.source_evidence_id) is not str
        or not prepared.source_evidence_id
        or type(prepared.signer_user_id) is not str
        or not prepared.signer_user_id
        or type(prepared.binding_sha256) is not str
        or len(prepared.binding_sha256) != 64
        or type(prepared.source_pdf_sha256) is not str
        or len(prepared.source_pdf_sha256) != 64
    ):
        raise ValidationError("Untrusted attestation preparation result.")

    payload = {
        "purpose": PURPOSE,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "source_evidence_id": prepared.source_evidence_id,
        "source_pdf_sha256": prepared.source_pdf_sha256,
        "binding_sha256": prepared.binding_sha256,
        "signer_user_id": prepared.signer_user_id,
        "prepared_by_user_id": str(preparer.pk),
        "provider": "DOCUSIGN",
        "status": "OFFLINE_ATTESTATION_BINDING_NOT_SENT",
        "envelope_created": False,
        "provider_authenticated": False,
        "source_artifact_authenticated": False,
        "trusted_installation_evidence": False,
        "final_receipt_issuance_authorized": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }

    previous = list(ProjectEvidence.objects.filter(
        msr=msr, kind=KIND
    ))
    if len(previous) > 1:
        raise ValidationError("Duplicate attestation preparation records.")
    if previous:
        record = previous[0]
        if (
            record.created_by_id != preparer.pk
            or record.msr_id != msr.pk
            or type(record.data) is not dict
            or record.data != payload
            or record.digest != canonical_hash(record.data)
        ):
            raise ValidationError(
                "Existing attestation preparation differs from request."
            )
        return record, False

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=KIND,
        created_by=preparer,
        data=payload,
        digest=canonical_hash(payload),
    )
    audit(
        preparer,
        "installation.attestation_prepared",
        project.pk,
        {
            "evidence_id": str(record.pk),
            "source_evidence_id": prepared.source_evidence_id,
            "binding_sha256": prepared.binding_sha256,
            "provider_authenticated": False,
            "receipt_authorized": False,
        },
    )
    return record, True
