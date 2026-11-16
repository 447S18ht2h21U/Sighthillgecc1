"""Development-only, durable Installation Manager draft intent.

This records CEO/Sales Manager authorization of a specific offline
draft fingerprint. It does not authorize provider creation or sending.
"""
import json
import os
import re
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import Project, ProjectEvidence, User
from core.installation_docusign_envelope_4962 import OfflineInstallationEnvelope
from core.installation_provider_oauth_4979 import Role, audit, canonical_hash
from core.installation_sandbox_draft_transport_5173 import (
    _validate_draft_payload,
)

KIND = "IM_DRAFT_INTENT_5179"
FLAG = "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED"
HEX = re.compile(r"^[0-9a-f]{64}$")


def _gate(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(FLAG) != "1"
    ):
        raise PermissionDenied("Inspection draft authorization disabled.")

    if (
        actor is None
        or not getattr(actor, "pk", None)
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None)
        not in (Role.CEO, Role.SALES_MANAGER)
    ):
        raise PermissionDenied("CEO or Sales Manager authorization required.")

    reviewer = User.objects.filter(pk=actor.pk, is_active=True).first()

    if reviewer is None or reviewer.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        raise PermissionDenied("Current authorized role required.")

    return reviewer


def _fingerprint(envelope):
    if type(envelope) is not OfflineInstallationEnvelope:
        raise ValidationError("Existing offline inspection envelope required.")

    if (
        envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.envelope_id is not None
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
    ):
        raise ValidationError("Offline inspection envelope is not a draft.")

    payload = _validate_draft_payload(envelope.request)

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")

    return sha256(encoded).hexdigest()


@transaction.atomic
def record_draft_intent(
    *, actor, project_id, envelope, confirmed
):
    """Record an immutable-intent evidence row, without provider activity."""
    reviewer = _gate(actor)

    if confirmed is not True:
        raise ValidationError("Explicit draft authorization required.")

    fingerprint = _fingerprint(envelope)

    if not HEX.fullmatch(fingerprint):
        raise ValidationError("Invalid inspection package fingerprint.")

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active development project required.")

    msr = project.current_approved

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    # The exact unsigned package must belong to this approved project
    # and MSR version. A valid hash from another project is insufficient.
    if (
        envelope.project_id != str(project.pk)
        or envelope.approved_msr_id != str(msr.pk)
        or envelope.approved_msr_version != str(msr.number)
    ):
        raise ValidationError(
            "Inspection draft does not match current approved MSR."
        )

    if ProjectEvidence.objects.filter(
        msr=msr, kind=KIND
    ).exists():
        raise ValidationError(
            "An inspection draft authorization already exists. "
            "Review its history; do not duplicate it."
        )

    data = {
        "schema": "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1",
        "state": "DRAFT_INTENT_RECORDED",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": str(msr.number),
        "authorized_by_id": str(reviewer.pk),
        "draft_payload_sha256": fingerprint,
        "authorized_at": timezone.now().isoformat(),
        "provider_draft_created": False,
        "provider_request_authorized": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "inspection_findings_verified": False,
        "receipt_issuance_authorized": False,
        "project_completion_authorized": False,
    }

    digest = canonical_hash(data)

    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=KIND,
        created_by=reviewer,
        data=data,
        digest=digest,
    )

    audit(
        reviewer,
        "installation.inspection_sandbox_draft_intent_recorded",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "draft_payload_sha256": fingerprint,
            "digest": digest,
            "provider_request_authorized": False,
            "send_authorized": False,
        },
    )

    return {
        "status": "DRAFT_INTENT_RECORDED",
        "evidence_id": str(evidence.pk),
        "digest": digest,
        "provider_draft_created": False,
        "provider_request_authorized": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "project_completion_authorized": False,
    }