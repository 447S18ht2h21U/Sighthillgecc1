"""Read-only project audit of persisted Installation Inspection evidence.

Both inspection findings and optional Receipt feedback remain UNVERIFIED
observations until separately authenticated provider/customer evidence
is established.

No DocuSign network requests, evidence writes, corrective-action
creation, Receipt issuance, or project completion.
"""
from dataclasses import dataclass
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .models import (
    Project,
    User,
    Role,
    InstallationInspectionEvidence4969,
)
from .installation_evidence_retention_4969 import (
    verify_retained_inspection_bytes,
)
from .receipt_feedback_audit_readback_4958 import (
    read_project_receipt_audit,
)


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_QUESTIONS = tuple(f"inspection_{i}" for i in range(1, 6))


@dataclass(frozen=True)
class RetainedInspectionProjectAudit4971:
    project_id: str
    approved_msr_id: str
    inspection_evidence_id: str
    intended_manager_id: str
    inspection_findings: tuple
    negative_inspection_ids: tuple
    inspection_pdf_sha256: str
    inspection_certificate_sha256: str
    receipt_feedback_evidence_id: str | None
    receipt_comparison: object | None
    status: str = "RETAINED_INSPECTION_AUDIT_UNVERIFIED"
    retained_bytes_integrity_verified: bool = True
    provider_origin_authenticated: bool = False
    manager_signature_verified: bool = False
    manager_signed_date_verified: bool = False
    customer_feedback_authenticated: bool = False
    corrective_actions_created: bool = False
    receipt_issuance_authorized: bool = False
    project_completion_authorized: bool = False


def read_retained_inspection_project_audit(
    *,
    actor,
    project_id,
    inspection_evidence_id,
    receipt_feedback_evidence_id=None,
):
    """Rebind exact retained evidence to its current approved project."""
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_IM_EVIDENCE_RETENTION_TEST_ENABLED") != "1"
    ):
        raise PermissionDenied("Inspection evidence audit disabled.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated reviewer required.")

    reviewer = User.objects.filter(
        pk=actor.pk,
        is_active=True,
    ).first()
    if reviewer is None or reviewer.role not in (
        Role.CEO, Role.COMPTROLLER
    ):
        raise PermissionDenied("Authorized reviewer required.")

    project = (
        Project.objects.select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )
    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    record = (
        InstallationInspectionEvidence4969.objects
        .select_related("msr", "created_by")
        .filter(pk=inspection_evidence_id, msr=msr)
        .first()
    )
    if record is None:
        raise ValidationError("Project-bound inspection evidence missing.")

    proof = verify_retained_inspection_bytes(record)
    if (
        proof.get("integrity_verified") is not True
        or proof.get("provider_authenticated") is not False
        or proof.get("signatures_verified") is not False
        or proof.get("completion_authorized") is not False
    ):
        raise ValidationError("Retained inspection trust boundary failed.")

    metadata = record.source_data
    if type(metadata) is not dict:
        raise ValidationError("Inspection metadata malformed.")

    manager_id = metadata.get("intended_manager_id")
    manager = User.objects.filter(
        pk=manager_id,
        is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()
    if manager is None:
        raise ValidationError("Assigned Installation Manager invalid.")

    if (
        metadata.get("state") != "UNVERIFIED_RETAINED"
        or metadata.get("provider_authenticated") is not False
        or metadata.get("signatures_verified") is not False
        or metadata.get("dates_verified") is not False
        or metadata.get("completion_authorized") is not False
        or metadata.get("project_id") != str(project.pk)
        or metadata.get("msr_id") != str(msr.pk)
        or metadata.get("msr_version") != str(msr.number)
        or metadata.get("bundle_digest") != record.bundle_digest
        or metadata.get("signed_pdf_sha256") != record.signed_pdf_sha256
        or metadata.get("certificate_sha256") != record.certificate_sha256
        or type(record.bundle_digest) is not str
        or not _HEX64.fullmatch(record.bundle_digest)
    ):
        raise ValidationError("Inspection evidence bindings inconsistent.")

    stored_findings = metadata.get("inspection_findings")
    if type(stored_findings) is not list or len(stored_findings) != 5:
        raise ValidationError("Five inspection findings required.")

    findings = []
    for index, entry in enumerate(stored_findings):
        if (
            type(entry) is not list
            or len(entry) != 2
            or entry[0] != _QUESTIONS[index]
            or type(entry[1]) is not str
            or entry[1] not in ("YES", "NO")
        ):
            raise ValidationError("Retained inspection finding invalid.")
        findings.append((entry[0], entry[1]))

    findings = tuple(findings)
    negatives = tuple(
        key for key, answer in findings if answer == "NO"
    )

    stored_negatives = metadata.get("negative_inspection_ids")
    if (
        type(stored_negatives) is not list
        or tuple(stored_negatives) != negatives
    ):
        raise ValidationError("Retained negative findings mismatch.")

    receipt_comparison = None
    receipt_id = None

    if receipt_feedback_evidence_id is not None:
        receipt_comparison = read_project_receipt_audit(
            actor=reviewer,
            project_id=project.pk,
            feedback_evidence_id=receipt_feedback_evidence_id,
            inspection_source_evidence_id=str(record.pk),
            manager_findings=dict(findings),
        )

        if (
            receipt_comparison.project_id != str(project.pk)
            or receipt_comparison.approved_msr_id != str(msr.pk)
            or receipt_comparison.customer_provenance_authenticated is not False
            or receipt_comparison.inspection_signature_verified is not False
            or receipt_comparison.project_completion_authorized is not False
        ):
            raise ValidationError("Receipt audit asserted unsupported trust.")

        receipt_id = str(receipt_comparison.feedback_evidence_id)

    return RetainedInspectionProjectAudit4971(
        project_id=str(project.pk),
        approved_msr_id=str(msr.pk),
        inspection_evidence_id=str(record.pk),
        intended_manager_id=str(manager.pk),
        inspection_findings=findings,
        negative_inspection_ids=negatives,
        inspection_pdf_sha256=record.signed_pdf_sha256,
        inspection_certificate_sha256=record.certificate_sha256,
        receipt_feedback_evidence_id=receipt_id,
        receipt_comparison=receipt_comparison,
    )
