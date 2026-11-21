"""Read-only, isolated inspection draft attempt status.

A reservation with no recorded provider result requires manual review.
Never retry automatically, send, or assert a verified signature.
"""
from django.core.exceptions import ValidationError

from core.documents import canonical_hash
from core.models import Project, ProjectEvidence
from core.installation_draft_handoff_5258 import _isolated_gate
from core.installation_draft_tracking_5265 import (
    RESERVATION_KIND, RESULT_KIND,
)
from core.installation_sandbox_draft_transport_5173 import _uuid


def status(*, actor, project_id):
    _isolated_gate(actor)

    project = Project.objects.select_related(
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
    ):
        raise ValidationError("Current approved MSR required.")

    reservations = list(
        ProjectEvidence.objects.filter(
            msr__project=project, kind=RESERVATION_KIND
        )
    )
    results = list(
        ProjectEvidence.objects.filter(
            msr__project=project, kind=RESULT_KIND
        )
    )

    if len(reservations) > 1 or len(results) > 1:
        raise ValidationError("Conflicting draft tracking records.")

    base = {
        "project_id": str(project.pk),
        "read_only": True,
        "automatic_retry_allowed": False,
        "send_authorized": False,
        "signature_verified": False,
        "receipt_authorized": False,
        "completion_authorized": False,
        "reservation_id": None,
        "provider_envelope_id": None,
    }

    if not reservations:
        if results:
            raise ValidationError("Orphaned provider draft result.")
        return {
            **base,
            "state": "NO_DRAFT_ATTEMPT",
            "manual_reconciliation_required": False,
        }

    reservation = reservations[0]
    r = reservation.data

    if (
        type(r) is not dict
        or reservation.msr_id != msr.pk
        or reservation.digest != canonical_hash(r)
        or r.get("schema") != "GECC_IM_DRAFT_RESERVATION_5265_V1"
        or r.get("state") != "RESERVED_PROVIDER_OUTCOME_UNKNOWN"
        or r.get("project_id") != str(project.pk)
        or r.get("msr_id") != str(msr.pk)
        or r.get("msr_version") != str(msr.number)
        or r.get("reserved_by_id") != str(reservation.created_by_id)
        or r.get("send_authorized") is not False
        or r.get("signature_verified") is not False
        or r.get("completion_authorized") is not False
        or not r.get("authorization_id")
        or not r.get("draft_payload_sha256")
    ):
        raise ValidationError("Draft reservation integrity failed.")

    if not results:
        return {
            **base,
            "state": "PROVIDER_OUTCOME_UNKNOWN",
            "manual_reconciliation_required": True,
            "reservation_id": str(reservation.pk),
        }

    result = results[0]
    d = result.data

    if (
        type(d) is not dict
        or result.msr_id != msr.pk
        or result.digest != canonical_hash(d)
        or d.get("schema") != "GECC_IM_DRAFT_RESULT_5265_V1"
        or d.get("state") != "SANDBOX_DRAFT_CREATED_NOT_SENT"
        or d.get("project_id") != str(project.pk)
        or d.get("msr_id") != str(msr.pk)
        or d.get("msr_version") != str(msr.number)
        or d.get("reservation_id") != str(reservation.pk)
        or d.get("authorization_id") != r["authorization_id"]
        or d.get("draft_payload_sha256")
            != r["draft_payload_sha256"]
        or result.created_by_id != reservation.created_by_id
        or d.get("send_authorized") is not False
        or d.get("signature_verified") is not False
        or d.get("completion_authorized") is not False
    ):
        raise ValidationError("Provider draft result integrity failed.")

    _uuid(d.get("provider_account_id"))
    envelope_id = _uuid(d.get("provider_envelope_id"))

    return {
        **base,
        "state": "SANDBOX_DRAFT_CREATED_NOT_SENT",
        "manual_reconciliation_required": False,
        "reservation_id": str(reservation.pk),
        "provider_envelope_id": envelope_id,
    }
