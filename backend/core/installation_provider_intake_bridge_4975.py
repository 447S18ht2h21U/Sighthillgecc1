"""Offline bridge from sandbox readback to UNVERIFIED inspection intake.

A readback object may be constructed or injected by tests. It cannot
authenticate the provider, signer, signature, or certificate by itself.
Requires later independently established envelope binding and provenance.
Never sends envelopes, accesses the network, or modifies the database.
"""
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_provider_readback_4972 import (
    SandboxInspectionReadback4972,
)
from .installation_docusign_envelope_4962 import (
    OfflineInstallationEnvelope,
)
from .installation_docusign_response_4964 import (
    parse_untrusted_docusign_inspection_response,
)
from .installation_docusign_evidence_intake_4966 import (
    assemble_unverified_inspection_evidence,
)
from .installation_inspection_form_4945 import INSPECTION_IDS


@dataclass(frozen=True)
class OfflineInspectionReadbackBridge4975:
    account_id: str
    envelope_id: str
    project_id: str
    approved_msr_id: str
    observation_sha256: str
    evidence_bundle_sha256: str
    evidence_bundle: object
    status: str = "READBACK_LINKED_PROVENANCE_UNVERIFIED"
    provider_origin_authenticated: bool = False
    envelope_binding_authenticated: bool = False
    signer_identity_verified: bool = False
    signature_verified: bool = False
    signed_date_verified: bool = False
    certificate_verified: bool = False
    evidence_retained: bool = False
    corrective_actions_created: bool = False
    completion_authorized: bool = False


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical provider identifier required.")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(
            "Canonical provider identifier required."
        ) from None
    return value


def link_unverified_inspection_readback(
    *,
    envelope,
    readback,
    expected_account_id,
    expected_envelope_id,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline provider bridge disabled.")

    if (
        type(envelope) is not OfflineInstallationEnvelope
        or type(readback) is not SandboxInspectionReadback4972
    ):
        raise ValidationError("Expected offline envelope and readback.")

    account = _uuid(expected_account_id)
    envelope_id = _uuid(expected_envelope_id)
    if (
        readback.account_id != account
        or readback.envelope_id != envelope_id
        or readback.status != "SANDBOX_READBACK_NOT_INDEPENDENTLY_VERIFIED"
        or readback.provider_signature_verified is not False
        or readback.signer_identity_verified is not False
        or readback.inspection_findings_verified is not False
        or readback.completion_authorized is not False
    ):
        raise ValidationError("Readback identity or trust boundary mismatch.")

    summary = readback.envelope_summary
    if (
        type(summary) is not dict
        or summary.get("envelopeId") != envelope_id
        or summary.get("status") != "completed"
    ):
        raise ValidationError("Completed envelope identity not established.")

    if (
        envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.envelope_id is not None
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
    ):
        raise ValidationError("Source package is not an offline draft.")

    planned = envelope.request.get("recipients", {}).get("signers")
    observed = readback.recipient_summary.get("signers") if (
        type(readback.recipient_summary) is dict
    ) else None

    if (
        type(planned) is not list or len(planned) != 1
        or type(observed) is not list or len(observed) != 1
        or type(planned[0]) is not dict
        or type(observed[0]) is not dict
    ):
        raise ValidationError("Exactly one manager signer is required.")

    intended = planned[0]
    returned = observed[0]
    if (
        intended.get("recipientId") != "1"
        or returned.get("recipientId") != "1"
        or returned.get("name") != intended.get("name")
        or returned.get("email") != intended.get("email")
        or returned.get("status") != "completed"
    ):
        raise ValidationError("Returned recipient differs from intended signer.")

    response = readback.recipient_tabs
    if type(response) is not dict:
        raise ValidationError("Invalid provider-shaped tab response.")

    groups = response.get("radioGroupTabs")
    if type(groups) is not list or len(groups) != 5:
        raise ValidationError("Five manager responses required.")

    # Only answer values enter the strict existing parser. Unknown
    # question groups and duplicate selections are rejected there.
    normalized = []
    for group in groups:
        if type(group) is not dict:
            raise ValidationError("Invalid question group.")
        radios = group.get("radios")
        if type(radios) is not list or len(radios) != 2:
            raise ValidationError("Invalid returned radio choices.")
        normalized.append({
            "groupName": group.get("groupName"),
            "radios": [
                {
                    "value": radio.get("value"),
                    "selected": radio.get("selected"),
                }
                for radio in radios
                if type(radio) is dict
            ],
        })

    if {
        group["groupName"] for group in normalized
    } != set(INSPECTION_IDS):
        raise ValidationError("Manager question set differs.")

    observation = parse_untrusted_docusign_inspection_response(
        envelope=envelope,
        purported_envelope_id=envelope_id,
        recipient_tabs={"radioGroupTabs": normalized},
    )

    if (
        sha256(readback.signed_pdf).hexdigest()
        != readback.signed_pdf_sha256
        or sha256(readback.certificate_pdf).hexdigest()
        != readback.certificate_sha256
    ):
        raise ValidationError("Readback document fingerprint mismatch.")

    bundle = assemble_unverified_inspection_evidence(
        envelope=envelope,
        observation=observation,
        claimed_envelope_status=summary["status"],
        claimed_recipient_id=returned["recipientId"],
        signed_pdf=readback.signed_pdf,
        certificate_pdf=readback.certificate_pdf,
    )

    if (
        bundle.authenticated_provider_readback is not False
        or bundle.signer_identity_verified is not False
        or bundle.provider_signature_verified is not False
        or bundle.completion_authorized is not False
    ):
        raise ValidationError("Evidence bundle asserted unsupported trust.")

    return OfflineInspectionReadbackBridge4975(
        account_id=account,
        envelope_id=envelope_id,
        project_id=envelope.project_id,
        approved_msr_id=envelope.approved_msr_id,
        observation_sha256=observation.observation_sha256,
        evidence_bundle_sha256=bundle.bundle_sha256,
        evidence_bundle=bundle,
    )
