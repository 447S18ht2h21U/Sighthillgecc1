
'''Development-only, approved-MSR-bound expedited signing attempt.

This service does not create or send DocuSign envelopes.
No production route invokes it, and no installation authority is granted.
'''
from datetime import date
from uuid import UUID

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import (
    MSR, Role, ExpeditedSigningAttempt, ProjectEvidence,
)
from .expedited_envelope_preview_4568 import build_unified_envelope_preview
from .expedited_offline_envelope_4568 import assemble_offline_candidate

ALLOWED_ROLES = (Role.SALES_MANAGER, Role.CEO)
RECIPIENT_ROLES = (
    "CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER",
)


def _canonical_uuid(value):
    try:
        normalized = str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid MSR identifier.") from None
    if str(value) != normalized:
        raise ValidationError("Noncanonical MSR identifier.")
    return normalized


def prepare_expedited_attempt(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Expedited attempt creation is not live-enabled.")

    if (
        actor is None
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) not in ALLOWED_ROLES
        or not getattr(actor, "pk", None)
    ):
        raise PermissionDenied("Sales Manager or CEO required.")

    preview = build_unified_envelope_preview(
        actor=actor, project_id=project_id
    )
    offline = assemble_offline_candidate(preview=preview)

    if (
        preview.get("send_authorized") is not False
        or preview.get("installation_authorized") is not False
        or offline.get("send_authorized") is not False
        or offline.get("installation_authorized") is not False
    ):
        raise ValidationError("Unsendable attempt preconditions changed.")

    msr_id = _canonical_uuid(preview.get("msr_id"))
    try:
        proposed_date = date.fromisoformat(preview["proposed_date"])
    except (KeyError, ValueError, TypeError):
        raise ValidationError("Invalid proposed installation date.") from None

    manifest = []
    signers = offline["recipients"]["signers"]
    if len(signers) != 3:
        raise ValidationError("Three recipient identities required.")

    for number, (role, signer) in enumerate(
        zip(RECIPIENT_ROLES, signers), start=1
    ):
        if (
            signer.get("role") != role
            or signer.get("recipientId") != str(number)
            or signer.get("routingOrder") != str(number)
            or not signer.get("name")
            or not signer.get("email")
        ):
            raise ValidationError("Approved signer manifest differs.")

        manifest.append({
            "role": role,
            "recipient_id": str(number),
            "routing_order": str(number),
            "name": signer["name"],
            "email": signer["email"].strip().casefold(),
        })

    source_digest = canonical_hash({
        "msr_id": msr_id,
        "snapshot_sha256": preview["snapshot_sha256"],
        "proposed_date": proposed_date.isoformat(),
        "recipients": manifest,
        "document_hashes": {
            str(item["documentId"]): canonical_hash(
                item["documentBase64"]
            )
            for item in offline["documents"]
        },
    })

    return {
        "msr_id": msr_id,
        "project_id": str(project_id),
        "snapshot_sha256": preview["snapshot_sha256"],
        "proposed_date": proposed_date,
        "recipient_manifest": manifest,
        "source_digest": source_digest,
        "send_authorized": False,
        "installation_authorized": False,
    }


@transaction.atomic
def create_expedited_attempt(*, actor, project_id):
    plan = prepare_expedited_attempt(
        actor=actor, project_id=project_id
    )

    record = MSR.objects.select_for_update().get(pk=plan["msr_id"])
    if (
        record.status != "APPROVED"
        or str(record.project_id) != plan["project_id"]
        or canonical_hash(record.snapshot) != plan["snapshot_sha256"]
    ):
        raise ValidationError("Approved MSR version changed.")

    # Do not silently reuse an existing attempt or regenerate an
    # envelope for the same canonical source.
    if ExpeditedSigningAttempt.objects.filter(
        msr=record, source_digest=plan["source_digest"]
    ).exists():
        raise ValidationError("Signing attempt already recorded.")

    attempt = ExpeditedSigningAttempt.objects.create(
        msr=record,
        initiated_by=actor,
        snapshot_sha256=plan["snapshot_sha256"],
        proposed_date=plan["proposed_date"],
        recipient_manifest=plan["recipient_manifest"],
        source_digest=plan["source_digest"],
    )

    evidence_data = {
        "attempt_id": str(attempt.pk),
        "msr_id": plan["msr_id"],
        "snapshot_sha256": plan["snapshot_sha256"],
        "source_digest": plan["source_digest"],
        "state": "PREPARED_NOT_SENT",
        "provider_envelope_id": None,
        "send_authorized": False,
        "installation_authorized": False,
    }
    ProjectEvidence.objects.create(
        msr=record,
        kind="EXPEDITED_SIGNING_ATTEMPT",
        created_by=actor,
        data=evidence_data,
        digest=canonical_hash(evidence_data),
    )

    return {
        "attempt_id": str(attempt.pk),
        "msr_id": plan["msr_id"],
        "source_digest": plan["source_digest"],
        "status": "PREPARED_NOT_SENT",
        "provider_envelope_id": None,
        "send_authorized": False,
        "installation_authorized": False,
    }
