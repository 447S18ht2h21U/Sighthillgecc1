"""Offline assembly of a DocuSign Installation Inspection envelope request.

No API call, no envelope creation, no sending, and no provider trust.
The internal document is signed only by its assigned Installation Manager.
Only a separately authorized preparer may obtain the upstream contract.
"""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import base64
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_docusign_contract_4959 import (
    UnsignedInstallationSigningContract,
)
from .installation_docusign_placement_4960 import (
    OfflineInspectionTabPlan,
)
from .installation_docusign_tabs_4961 import (
    build_offline_recipient_tabs,
)


@dataclass(frozen=True)
class OfflineInstallationEnvelope:
    request: dict
    project_id: str
    approved_msr_id: str
    approved_msr_version: str
    signer_user_id: str
    unsigned_pdf_sha256: str
    signing_contract_sha256: str
    placement_sha256: str
    envelope_package_sha256: str
    state: str = "LOCAL_DRAFT_NOT_SUBMITTED"
    envelope_id: None = None
    provider_validated: bool = False
    provider_tabs_installed: bool = False
    provider_signed: bool = False
    provider_date_verified: bool = False
    inspection_findings_verified: bool = False
    customer_survey_authenticated: bool = False
    corrective_actions_created: bool = False
    receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def _canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def build_offline_installation_envelope(
    *, contract, plan, unsigned_pdf
):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
    ):
        raise PermissionDenied("Offline envelope assembly disabled.")

    if type(contract) is not UnsignedInstallationSigningContract:
        raise ValidationError("Unsigned signing contract required.")
    if type(plan) is not OfflineInspectionTabPlan:
        raise ValidationError("Offline tab placement required.")
    if type(unsigned_pdf) is not bytes:
        raise ValidationError("Exact unsigned inspection PDF required.")

    if (
        len(unsigned_pdf) > 5_000_000
        or len(unsigned_pdf) < 100
        or not unsigned_pdf.startswith(b"%PDF-")
        or not unsigned_pdf.rstrip().endswith(b"%%EOF")
        or sha256(unsigned_pdf).hexdigest()
        != contract.unsigned_pdf_sha256
        or contract.project_id.strip() != contract.project_id
        or not contract.project_id
        or not contract.approved_msr_id
        or not contract.approved_msr_version
        or not contract.preparation_evidence_id
        or not contract.source_evidence_id
        or not contract.signer_user_id
        or not contract.signer_email
        or not contract.signer_name
        or contract.envelope_id is not None
        or contract.provider_tabs_installed is not False
        or contract.provider_signature_verified is not False
        or contract.inspection_findings_verified is not False
        or contract.project_completion_authorized is not False
    ):
        raise ValidationError("Untrusted or mismatched inspection document.")

    # Refuse any response, whether real or fabricated, that claims
    # provider trust has already been established.
    payload = build_offline_recipient_tabs(
        contract=contract, plan=plan
    )

    if (
        payload.provider_validated is not False
        or payload.tabs_installed is not False
        or payload.envelope_created is not False
        or payload.findings_verified is not False
        or payload.completion_authorized is not False
        or len(payload.tabs.get("radioGroupTabs", [])) != 5
        or len(payload.tabs.get("signHereTabs", [])) != 1
        or len(payload.tabs.get("dateSignedTabs", [])) != 1
    ):
        raise ValidationError("Unsigned recipient tabs invalid.")

    # 'created' is the provider's DRAFT state, not 'sent'.
    # This function constructs bytes only; it never transmits them.
    request = {
        "emailSubject": "GECC Internal Installation Inspection Attestation",
        "status": "created",
        "documents": [{
            "documentId": "1",
            "name": "GECC Installation Inspection Attestation",
            "fileExtension": "pdf",
            "documentBase64": base64.b64encode(
                unsigned_pdf
            ).decode("ascii"),
        }],
        "recipients": {
            "signers": [{
                "recipientId": "1",
                "routingOrder": "1",
                "name": contract.signer_name,
                "email": contract.signer_email,
                "tabs": deepcopy(payload.tabs),
            }],
        },
    }

    if len(request["recipients"]["signers"]) != 1:
        raise ValidationError("Exactly one Installation Manager signer required.")
    if request["status"] != "created":
        raise ValidationError("Only offline draft status permitted.")

    fingerprint_material = {
        "schema": "GECC_IM_OFFLINE_ENVELOPE_4962_V1",
        "project_id": contract.project_id,
        "msr_id": contract.approved_msr_id,
        "msr_version": contract.approved_msr_version,
        "source_evidence_id": contract.source_evidence_id,
        "source_pdf_sha256": contract.source_pdf_sha256,
        "preparation_evidence_id": contract.preparation_evidence_id,
        "signer_user_id": contract.signer_user_id,
        "contract_sha256": contract.contract_sha256,
        "placement_sha256": plan.plan_sha256,
        "tab_payload_sha256": payload.payload_sha256,
        "request": request,
    }

    return OfflineInstallationEnvelope(
        request=request,
        project_id=contract.project_id,
        approved_msr_id=contract.approved_msr_id,
        approved_msr_version=contract.approved_msr_version,
        signer_user_id=contract.signer_user_id,
        unsigned_pdf_sha256=contract.unsigned_pdf_sha256,
        signing_contract_sha256=contract.contract_sha256,
        placement_sha256=plan.plan_sha256,
        envelope_package_sha256=sha256(
            _canonical_bytes(fingerprint_material)
        ).hexdigest(),
    )
