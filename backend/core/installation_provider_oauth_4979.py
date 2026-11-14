"""Development-only OAuth handoff for Installation Inspection readback.

The standard DocuSign OAuth callback validates the account and supplies
an ephemeral access token. This operation NEVER receives authorization
to send envelopes, never stores the bearer, and cannot certify signer
identity or authorize project completion.

A successful readback establishes that the authenticated sandbox account
returned bytes matching the already retained UNVERIFIED documents.
It does not replace provider signature/date verification.
"""
import os
from hashlib import sha256
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from . import docusign
from .documents import canonical_hash
from .models import (
    Project, ProjectEvidence, User, Role,
    InstallationInspectionEvidence4969,
)
from .installation_envelope_binding_4976 import KIND
from .installation_evidence_retention_4969 import (
    verify_retained_inspection_bytes,
)
from .installation_provider_readback_4972 import (
    retrieve_inspection_sandbox_evidence,
)

OPERATION = "SANDBOX_INSPECTION_READ"


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical UUID required.")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Canonical UUID required.") from None
    return value


def _gate(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_IM_OAUTH_READ_ENABLED") != "1"
        or os.environ.get("GECC_IM_PROVIDER_READBACK_ENABLED") != "1"
    ):
        raise PermissionDenied("Inspection OAuth readback disabled.")

    if (
        actor is None
        or not getattr(actor, "pk", None)
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied("Comptroller sandbox reviewer required.")

    reviewer = User.objects.filter(
        pk=actor.pk, is_active=True, role=Role.COMPTROLLER
    ).first()
    if reviewer is None:
        raise PermissionDenied("Active Comptroller required.")
    return reviewer


def _binding(*, reviewer, project_id, binding_id, account_id=None):
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

    evidence = ProjectEvidence.objects.filter(
        pk=binding_id, msr=msr, kind=KIND
    ).first()
    if evidence is None or type(evidence.data) is not dict:
        raise ValidationError("Inspection envelope association missing.")

    data = evidence.data
    if (
        evidence.digest != canonical_hash(data)
        or data.get("state") != "ENVELOPE_ASSOCIATION_UNVERIFIED"
        or data.get("provider_authenticated") is not False
        or data.get("signer_verified") is not False
        or data.get("signed_date_verified") is not False
        or data.get("completion_authorized") is not False
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != str(msr.number)
    ):
        raise ValidationError("Inspection envelope association invalid.")

    account = _uuid(data.get("provider_account_id"))
    envelope_id = _uuid(data.get("provider_envelope_id"))
    if account_id is not None and account != _uuid(account_id):
        raise ValidationError("Provider account identity changed.")

    retained = InstallationInspectionEvidence4969.objects.filter(
        pk=data.get("retained_inspection_id"), msr=msr
    ).first()
    if retained is None:
        raise ValidationError("Retained inspection evidence missing.")

    integrity = verify_retained_inspection_bytes(retained)
    if (
        integrity.get("integrity_verified") is not True
        or integrity.get("provider_authenticated") is not False
        or retained.purported_envelope_id != envelope_id
        or retained.bundle_digest != data.get("retained_bundle_sha256")
        or retained.signed_pdf_sha256 != data.get("signed_pdf_sha256")
        or retained.certificate_sha256 != data.get("certificate_sha256")
        or retained.source_data.get("project_id") != str(project.pk)
        or retained.source_data.get("msr_id") != str(msr.pk)
        or retained.source_data.get("state") != "UNVERIFIED_RETAINED"
    ):
        raise ValidationError("Inspection retention binding invalid.")

    configured = docusign.configuration()
    if (
        type(configured) is not dict
        or configured.get("blockers")
        or configured.get("account_id") != account
        or docusign.BASE_URI != "https://demo.docusign.net"
    ):
        raise PermissionDenied("Configured sandbox account mismatch.")

    return project, evidence, retained, account, envelope_id


def begin(*, actor, project_id, binding_id, session_key):
    """Start an OAuth challenge only; perform NO envelope operations."""
    reviewer = _gate(actor)
    project, binding, retained, account, envelope_id = _binding(
        reviewer=reviewer,
        project_id=project_id,
        binding_id=binding_id,
    )
    if type(session_key) is not str or not session_key:
        raise PermissionDenied("Authenticated GECC session required.")

    # docusign.begin owns state, expiry, session binding, auditing
    # and the provider's authorization URL.
    response = docusign.begin(
        reviewer,
        session_key,
        context={
            "operation": OPERATION,
            "project_id": str(project.pk),
            "binding_id": str(binding.pk),
            "binding_digest": binding.digest,
            "retained_inspection_id": str(retained.pk),
            "account_id": account,
            "envelope_id": envelope_id,
            "reviewer_id": str(reviewer.pk),
            "send_enabled": False,
        },
    )
    return {
        **response,
        "operation": OPERATION,
        "send_enabled": False,
        "provider_signature_verified": False,
        "project_completion_authorized": False,
    }


def finish(actor, challenge, config, token):
    """Use validated callback token transiently; never persist it.

    This function is called ONLY by docusign.finish after OAuth
    callback state/session/account validation.
    """
    reviewer = _gate(actor)

    context = getattr(challenge, "context", None)
    if (
        type(context) is not dict
        or context.get("operation") != OPERATION
        or context.get("send_enabled") is not False
        or context.get("reviewer_id") != str(reviewer.pk)
        or getattr(challenge, "actor_id", None) != reviewer.pk
    ):
        raise PermissionDenied("OAuth operation context mismatch.")

    project, binding, retained, account, envelope_id = _binding(
        reviewer=reviewer,
        project_id=context.get("project_id"),
        binding_id=context.get("binding_id"),
        account_id=context.get("account_id"),
    )

    if (
        context.get("binding_digest") != binding.digest
        or context.get("retained_inspection_id") != str(retained.pk)
        or context.get("envelope_id") != envelope_id
        or type(config) is not dict
        or config.get("blockers")
        or config.get("account_id") != account
    ):
        raise PermissionDenied("OAuth association changed.")

    # The gateway receives the access token in memory. It uses a
    # fixed DocuSign sandbox host and strictly allowlisted GET paths.
    readback = retrieve_inspection_sandbox_evidence(
        actor=reviewer,
        account_id=account,
        envelope_id=envelope_id,
        bearer_token=token,
    )

    if (
        readback.account_id != account
        or readback.envelope_id != envelope_id
        or readback.envelope_summary.get("envelopeId") != envelope_id
        or readback.envelope_summary.get("status") != "completed"
        or readback.provider_signature_verified is not False
        or readback.completion_authorized is not False
        or readback.signed_pdf_sha256 != retained.signed_pdf_sha256
        or readback.certificate_sha256 != retained.certificate_sha256
        or sha256(readback.signed_pdf).hexdigest()
        != retained.signed_pdf_sha256
        or sha256(readback.certificate_pdf).hexdigest()
        != retained.certificate_sha256
        or readback.signed_pdf != bytes(retained.signed_pdf)
        or readback.certificate_pdf != bytes(retained.certificate_pdf)
    ):
        raise ValidationError(
            "Authenticated sandbox readback differs from retained evidence."
        )

    # No claim of signing authenticity: recipient tabs, signer identity,
    # signed date and provider certificate verification remain separate.
    # No raw PDFs, tokens, or signer personal data are returned.
    return {
        "operation": OPERATION,
        "status": "SANDBOX_READBACK_BYTES_MATCHED_SIGNER_UNVERIFIED",
        "project_id": str(project.pk),
        "binding_id": str(binding.pk),
        "retained_inspection_id": str(retained.pk),
        "account_id": account,
        "envelope_id": envelope_id,
        "signed_pdf_sha256": retained.signed_pdf_sha256,
        "certificate_sha256": retained.certificate_sha256,
        "readback_bytes_match": True,
        "provider_signature_verified": False,
        "signed_date_verified": False,
        "inspection_findings_verified": False,
        "corrective_actions_created": False,
        "project_completion_authorized": False,
        "send_enabled": False,
    }
