
'''Development-only recording of an UNVERIFIED sandbox envelope identity.

The binding records a claimed sandbox envelope association. It does
not authenticate its origin, authorize sending, or approve installation.
'''
import re
from uuid import UUID

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import docusign
from .documents import canonical_hash
from .models import (
    Role, ExpeditedSigningAttempt, ExpeditedEnvelopeBinding,
    ProjectEvidence,
)

ROLES = (Role.CEO, Role.SALES_MANAGER)
RECIPIENT_ROLES = (
    "CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER",
)


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical UUID string required.")
    try:
        canonical = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid UUID.") from None
    if value != canonical:
        raise ValidationError("Noncanonical UUID.")
    return canonical


@transaction.atomic
def bind_unverified_sandbox_envelope(
    *, actor, attempt_id, account_id, envelope_id,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Expedited envelope binding disabled.")

    if (
        actor is None
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) not in ROLES
        or not getattr(actor, "pk", None)
    ):
        raise PermissionDenied("Authorized initiating manager required.")

    attempt_id = _uuid(attempt_id)
    account_id = _uuid(account_id)
    envelope_id = _uuid(envelope_id)

    config = docusign.configuration()
    if (
        type(config) is not dict
        or config.get("blockers")
        or config.get("account_id") != account_id
    ):
        raise PermissionDenied("Configured sandbox account mismatch.")

    attempt = (
        ExpeditedSigningAttempt.objects.select_for_update()
        .select_related("msr__project")
        .get(pk=attempt_id)
    )
    msr = attempt.msr
    project = msr.project

    if (
        attempt.initiated_by_id != actor.pk
        or msr.status != "APPROVED"
        or project.current_approved_id != msr.pk
        or canonical_hash(msr.snapshot) != attempt.snapshot_sha256
        or not re.fullmatch(r"[0-9a-f]{64}", attempt.source_digest)
    ):
        raise ValidationError("Approved signing attempt integrity differs.")

    recipients = attempt.recipient_manifest
    if (
        type(recipients) is not list
        or len(recipients) != 3
    ):
        raise ValidationError("Three approved recipients required.")

    distinct_emails = set()
    for index, (role, signer) in enumerate(
        zip(RECIPIENT_ROLES, recipients), 1
    ):
        if type(signer) is not dict:
            raise ValidationError("Signer manifest malformed.")
        email = signer.get("email")
        if (
            signer.get("role") != role
            or signer.get("recipient_id") != str(index)
            or signer.get("routing_order") != str(index)
            or type(signer.get("name")) is not str
            or not signer["name"].strip()
            or type(email) is not str
            or "@" not in email
            or email != email.strip().casefold()
            or email in distinct_emails
        ):
            raise ValidationError("Recipient binding differs.")
        distinct_emails.add(email)

    evidence_rows = list(ProjectEvidence.objects.filter(
        msr=msr,
        kind="EXPEDITED_SIGNING_ATTEMPT",
        data__attempt_id=attempt_id,
    ))
    if len(evidence_rows) != 1:
        raise ValidationError("Immutable attempt evidence missing.")

    source = evidence_rows[0]
    data = source.data
    if (
        source.created_by_id != attempt.initiated_by_id
        or source.digest != canonical_hash(data)
        or data.get("attempt_id") != attempt_id
        or data.get("msr_id") != str(msr.pk)
        or data.get("source_digest") != attempt.source_digest
        or data.get("snapshot_sha256") != attempt.snapshot_sha256
        or data.get("state") != "PREPARED_NOT_SENT"
        or data.get("provider_envelope_id") is not None
        or data.get("send_authorized") is not False
        or data.get("installation_authorized") is not False
    ):
        raise ValidationError("Attempt evidence integrity failed.")

    if (
        ExpeditedEnvelopeBinding.objects.filter(attempt=attempt).exists()
        or ExpeditedEnvelopeBinding.objects.filter(
            provider_envelope_id=envelope_id
        ).exists()
    ):
        raise ValidationError("Envelope or signing attempt already bound.")

    payload = {
        "attempt_id": attempt_id,
        "msr_id": str(msr.pk),
        "source_digest": attempt.source_digest,
        "provider_account_id": account_id,
        "provider_envelope_id": envelope_id,
        "state": "SANDBOX_IDENTITY_CLAIM_UNVERIFIED",
        "provider_authenticated": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
    binding = ExpeditedEnvelopeBinding.objects.create(
        attempt=attempt,
        provider_account_id=account_id,
        provider_envelope_id=envelope_id,
        bound_by=actor,
        binding_digest=canonical_hash(payload),
    )
    evidence = {
        **payload,
        "binding_id": str(binding.pk),
    }
    ProjectEvidence.objects.create(
        msr=msr,
        kind="EXPEDITED_ENVELOPE_BINDING",
        created_by=actor,
        data=evidence,
        digest=canonical_hash(evidence),
    )

    return {
        "binding_id": str(binding.pk),
        "attempt_id": attempt_id,
        "msr_id": str(msr.pk),
        "envelope_id": envelope_id,
        "status": "SANDBOX_IDENTITY_CLAIM_UNVERIFIED",
        "provider_authenticated": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
