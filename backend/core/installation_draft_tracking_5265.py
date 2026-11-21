"""Isolated-only inspection draft reservation and provider result tracking.

Reservation commits BEFORE any provider call. A failed or ambiguous
provider attempt remains reserved and cannot be automatically retried.
No operational API, live signing, or project completion authority.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import Project, ProjectEvidence
from core.documents import canonical_hash
from core.services import audit
from core.installation_draft_handoff_5258 import (
    _isolated_gate, verify_handoff,
)
from core.installation_sandbox_handoff_5264 import (
    create_authorized_sandbox_draft,
)
from core.installation_sandbox_draft_transport_5173 import (
    _gate as transport_gate,
    _uuid,
)

RESERVATION_KIND = "IM_DRAFT_RESERVE_5265"
RESULT_KIND = "IM_DRAFT_RESULT_5265"


@transaction.atomic
def reserve(*, actor, project_id):
    """Reserve one draft attempt; never repeat after an uncertain result."""
    _isolated_gate(actor)

    verified = verify_handoff(
        actor=actor, project_id=project_id
    )
    if (
        verified.get("state") != "OFFLINE_DRAFT_HANDOFF_MATCHED"
        or verified.get("project_id") != str(project_id)
        or verified.get("read_only") is not True
        or not verified.get("authorization_id")
        or not verified.get("draft_payload_sha256")
        or any(
            verified.get(flag) is not False
            for flag in (
                "provider_request_authorized",
                "provider_envelope_created",
                "send_authorized",
                "provider_signature_verified",
                "receipt_issuance_authorized",
                "project_completion_authorized",
            )
        )
    ):
        raise ValidationError("Authorized draft handoff unavailable.")

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .get(pk=project_id)
    )
    msr = project.current_approved

    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved project required.")

    # Restrict to one attempted draft per project, including prior MSR
    # versions. An ambiguous provider response must never permit retry.
    if ProjectEvidence.objects.filter(
        msr__project=project,
        kind=RESERVATION_KIND,
    ).exists():
        raise ValidationError(
            "A DocuSign draft attempt is already reserved. "
            "Manual reconciliation is required."
        )

    data = {
        "schema": "GECC_IM_DRAFT_RESERVATION_5265_V1",
        "state": "RESERVED_PROVIDER_OUTCOME_UNKNOWN",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": str(msr.number),
        "authorization_id": verified["authorization_id"],
        "draft_payload_sha256": verified["draft_payload_sha256"],
        "reserved_by_id": str(actor.pk),
        "send_authorized": False,
        "signature_verified": False,
        "completion_authorized": False,
    }

    record = ProjectEvidence.objects.create(
        msr=msr,
        kind=RESERVATION_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )
    audit(
        actor,
        "installation.sandbox_draft_reserved",
        project.pk,
        {
            "reservation_id": str(record.pk),
            "authorization_id": verified["authorization_id"],
            "send_authorized": False,
        },
    )
    return record


@transaction.atomic
def record_created_draft(*, actor, reservation, response):
    """Append provider draft result, without attributing signature trust."""
    _isolated_gate(actor)

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .get(pk=reservation.msr.project_id)
    )
    msr = project.current_approved

    original = ProjectEvidence.objects.filter(
        pk=reservation.pk,
        kind=RESERVATION_KIND,
        msr=msr,
    ).first()

    if (
        original is None
        or project.state == "CANCELLED"
        or type(original.data) is not dict
        or original.digest != canonical_hash(original.data)
        or original.data.get("schema")
        != "GECC_IM_DRAFT_RESERVATION_5265_V1"
        or original.data.get("state")
        != "RESERVED_PROVIDER_OUTCOME_UNKNOWN"
        or original.data.get("project_id") != str(project.pk)
        or original.data.get("msr_id") != str(msr.pk)
        or original.data.get("msr_version") != str(msr.number)
        or original.data.get("reserved_by_id") != str(actor.pk)
        or original.created_by_id != actor.pk
        or original.data.get("send_authorized") is not False
        or original.data.get("signature_verified") is not False
        or original.data.get("completion_authorized") is not False
    ):
        raise ValidationError("Draft reservation integrity failed.")

    if ProjectEvidence.objects.filter(
        msr=msr, kind=RESULT_KIND
    ).exists():
        raise ValidationError("Provider draft result already recorded.")

    if (
        getattr(response, "status", None) != "created"
        or getattr(response, "sent", None) is not False
        or getattr(response, "signature_verified", None) is not False
        or getattr(response, "completion_authorized", None) is not False
    ):
        raise ValidationError("Untrusted provider draft response.")

    account = _uuid(getattr(response, "account_id", None))
    envelope = _uuid(getattr(response, "envelope_id", None))

    data = {
        "schema": "GECC_IM_DRAFT_RESULT_5265_V1",
        "state": "SANDBOX_DRAFT_CREATED_NOT_SENT",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": str(msr.number),
        "reservation_id": str(original.pk),
        "authorization_id": original.data["authorization_id"],
        "draft_payload_sha256": original.data["draft_payload_sha256"],
        "provider_account_id": account,
        "provider_envelope_id": envelope,
        "send_authorized": False,
        "signature_verified": False,
        "completion_authorized": False,
    }

    result = ProjectEvidence.objects.create(
        msr=msr,
        kind=RESULT_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )
    audit(
        actor,
        "installation.sandbox_draft_created_unsent",
        project.pk,
        {
            "reservation_id": str(original.pk),
            "result_id": str(result.pk),
            "envelope_id": envelope,
            "send_authorized": False,
        },
    )
    return result


def create_tracked_sandbox_draft(
    *, actor, project_id, account_id, bearer_token
):
    """Isolated-only entry point; never retry after reservation.

    No outer atomic transaction: the reservation must survive network
    errors and an uncertain provider outcome.
    """
    _isolated_gate(actor)
    transport_gate(actor)
    reservation = reserve(
        actor=actor, project_id=project_id
    )

    response = create_authorized_sandbox_draft(
        actor=actor,
        project_id=project_id,
        account_id=account_id,
        bearer_token=bearer_token,
    )

    record_created_draft(
        actor=actor,
        reservation=reservation,
        response=response,
    )
    return response
