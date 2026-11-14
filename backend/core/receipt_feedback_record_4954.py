"""Development-only retention of UNVERIFIED customer Receipt feedback.

ProjectEvidence is append-only through its model interface. This service
does not authenticate the customer, verify a Receipt's delivery, certify
the Installation Manager, generate work orders, or complete a project.
"""

import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .models import Project, ProjectEvidence, Role, User
from .receipt_feedback_binding_4951 import (
    UnverifiedReceiptFeedbackObservation,
    record_unverified_receipt_feedback,
)
from .services import audit


KIND = "RCPT_FEEDBACK_UNVERIFIED_4954"
STATUS = "UNVERIFIED_RECEIPT_FEEDBACK_OBSERVATION"
GATE = "GECC_RECEIPT_FEEDBACK_TEST_ENABLED"


def _gate():
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(GATE) != "1"
    ):
        raise PermissionDenied("Receipt feedback retention is disabled.")


def _payload(observation):
    if type(observation) is not UnverifiedReceiptFeedbackObservation:
        raise ValidationError("Receipt feedback observation required.")

    # Rebuild the observation's fingerprint rather than trusting a caller's
    # dataclass, status flags, or supplied digest.
    rebuilt = record_unverified_receipt_feedback(
        project_id=observation.project_id,
        approved_msr_id=observation.approved_msr_id,
        approved_msr_version=observation.approved_msr_version,
        receipt_evidence_id=observation.receipt_evidence_id,
        receipt_pdf_sha256=observation.receipt_pdf_sha256,
        recorded_by_actor_id=observation.recorded_by_actor_id,
        source_kind=observation.source_kind,
        survey_answers=dict(observation.answers),
    )
    if rebuilt != observation:
        raise ValidationError("Receipt observation integrity mismatch.")

    return {
        "schema": "GECC_RECEIPT_FEEDBACK_RECORD_4954_V1",
        "status": STATUS,
        "project_id": observation.project_id,
        "msr_id": observation.approved_msr_id,
        "msr_version": observation.approved_msr_version,
        "receipt_evidence_id": observation.receipt_evidence_id,
        "receipt_pdf_sha256": observation.receipt_pdf_sha256,
        "recorded_by_actor_id": observation.recorded_by_actor_id,
        "source_kind": observation.source_kind,
        "answers": [list(pair) for pair in observation.answers],
        "observation_sha256": observation.observation_sha256,
        "customer_authenticated": False,
        "receipt_delivery_verified": False,
        "provider_authenticated": False,
        "installation_inspection_verified": False,
        "corrective_actions_persisted": False,
        "completion_authorized": False,
    }


def verify_unverified_receipt_feedback(
    *, record, expected_project_id, expected_msr_id
):
    """Independent content verification; never customer authentication."""
    if (
        record is None
        or record.kind != KIND
        or str(record.msr_id) != str(expected_msr_id)
        or type(record.data) is not dict
        or record.data.get("project_id") != str(expected_project_id)
        or record.data.get("msr_id") != str(expected_msr_id)
        or record.digest != canonical_hash(record.data)
    ):
        raise ValidationError("Retained Receipt feedback binding invalid.")

    data = record.data
    if (
        data.get("schema") != "GECC_RECEIPT_FEEDBACK_RECORD_4954_V1"
        or data.get("status") != STATUS
        or str(record.created_by_id) != data.get("recorded_by_actor_id")
    ):
        raise ValidationError("Retained Receipt feedback metadata invalid.")

    for field in (
        "customer_authenticated",
        "receipt_delivery_verified",
        "provider_authenticated",
        "installation_inspection_verified",
        "corrective_actions_persisted",
        "completion_authorized",
    ):
        if data.get(field) is not False:
            raise ValidationError("Untrusted feedback asserted authority.")

    raw = data.get("answers")
    if type(raw) is not list or any(
        type(pair) is not list or len(pair) != 2 for pair in raw
    ):
        raise ValidationError("Invalid retained feedback answers.")

    rebuilt = record_unverified_receipt_feedback(
        project_id=data["project_id"],
        approved_msr_id=data["msr_id"],
        approved_msr_version=data["msr_version"],
        receipt_evidence_id=data["receipt_evidence_id"],
        receipt_pdf_sha256=data["receipt_pdf_sha256"],
        recorded_by_actor_id=data["recorded_by_actor_id"],
        source_kind=data["source_kind"],
        survey_answers=dict(raw),
    )
    if (
        [list(pair) for pair in rebuilt.answers] != raw
        or rebuilt.observation_sha256 != data["observation_sha256"]
        or _payload(rebuilt) != data
    ):
        raise ValidationError("Retained feedback has been altered.")

    return rebuilt


@transaction.atomic
def retain_unverified_receipt_feedback(
    *, actor, project_id, observation
):
    """Persist one unverified observation per Receipt reference/MSR.

    CEO/Comptroller-only access is a conservative development restriction,
    not a final policy decision about who may collect customer feedback.
    """
    _gate()

    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated recorder required.")

    recorder = User.objects.filter(
        pk=actor.pk, is_active=True
    ).first()
    if (
        recorder is None
        or recorder.role not in (Role.CEO, Role.COMPTROLLER)
    ):
        raise PermissionDenied("Authorized feedback recorder required.")

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

    payload = _payload(observation)
    if (
        payload["project_id"] != str(project.pk)
        or payload["msr_id"] != str(msr.pk)
        or payload["msr_version"] != str(msr.number)
        or payload["recorded_by_actor_id"] != str(recorder.pk)
    ):
        raise ValidationError("Project/MSR/recorder identity mismatch.")

    previous = list(
        ProjectEvidence.objects.filter(msr=msr, kind=KIND)
    )
    matching = [
        record for record in previous
        if type(record.data) is dict
        and record.data.get("receipt_evidence_id")
        == payload["receipt_evidence_id"]
    ]

    if len(matching) > 1:
        raise ValidationError("Duplicate Receipt feedback records.")
    if matching:
        record = matching[0]
        verify_unverified_receipt_feedback(
            record=record,
            expected_project_id=str(project.pk),
            expected_msr_id=str(msr.pk),
        )
        if (
            record.created_by_id != recorder.pk
            or record.data != payload
        ):
            raise ValidationError(
                "Conflicting observation for the same Receipt."
            )
        return record, False

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=KIND,
        created_by=recorder,
        data=payload,
        digest=canonical_hash(payload),
    )

    audit(
        recorder,
        "receipt.feedback_observation_recorded",
        project.pk,
        {
            "evidence_id": str(record.pk),
            "receipt_evidence_id": payload["receipt_evidence_id"],
            "observation_sha256": payload["observation_sha256"],
            "customer_authenticated": False,
        },
    )

    return record, True
