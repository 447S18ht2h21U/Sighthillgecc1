"""Read-only, development-gated project audit from persisted feedback.

A retained staff observation is NOT authenticated customer feedback.
Manager findings supplied to this function are also unverified inputs.
No provider signing, final Receipt, corrective-action write, or completion.
"""

from dataclasses import dataclass
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .models import Project, ProjectEvidence, Role, User
from .receipt_feedback_record_4954 import (
    KIND,
    verify_unverified_receipt_feedback,
)
from .receipt_feedback_binding_4951 import (
    build_unverified_receipt_audit_packet,
)


@dataclass(frozen=True)
class ReadOnlyProjectReceiptAudit:
    project_id: str
    approved_msr_id: str
    feedback_evidence_id: str
    packet: object
    status: str = "RETAINED_OBSERVATION_UNVERIFIED"
    customer_provenance_authenticated: bool = False
    receipt_pdf_independently_verified: bool = False
    inspection_signature_verified: bool = False
    work_orders_created: bool = False
    project_completion_authorized: bool = False


def read_project_receipt_audit(
    *,
    actor,
    project_id,
    feedback_evidence_id,
    inspection_source_evidence_id,
    manager_findings,
):
    """Bind persisted observation to current project/MSR; fail closed."""
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_RECEIPT_FEEDBACK_TEST_ENABLED") != "1"
    ):
        raise PermissionDenied("Receipt feedback audit is disabled.")

    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated reviewer required.")

    reviewer = User.objects.filter(
        pk=actor.pk, is_active=True
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
        raise ValidationError("Active persisted project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    record = ProjectEvidence.objects.filter(
        pk=feedback_evidence_id,
        msr=msr,
        kind=KIND,
    ).first()
    if record is None:
        raise ValidationError(
            "Project-bound feedback evidence not found."
        )

    observation = verify_unverified_receipt_feedback(
        record=record,
        expected_project_id=str(project.pk),
        expected_msr_id=str(msr.pk),
    )

    if observation.approved_msr_version != str(msr.number):
        raise ValidationError("Feedback MSR version mismatch.")

    packet = build_unverified_receipt_audit_packet(
        observation=observation,
        expected_project_id=str(project.pk),
        expected_msr_id=str(msr.pk),
        expected_msr_version=str(msr.number),
        expected_receipt_evidence_id=observation.receipt_evidence_id,
        expected_receipt_pdf_sha256=observation.receipt_pdf_sha256,
        inspection_source_evidence_id=inspection_source_evidence_id,
        manager_findings=manager_findings,
    )

    if (
        packet.independently_verified is not False
        or packet.corrective_actions_persisted is not False
        or packet.completion_authorized is not False
        or packet.audit.customer_provenance_verified is not False
        or packet.audit.completion_authorized is not False
    ):
        raise ValidationError("Unverified audit asserted authority.")

    return ReadOnlyProjectReceiptAudit(
        project_id=str(project.pk),
        approved_msr_id=str(msr.pk),
        feedback_evidence_id=str(record.pk),
        packet=packet,
    )
