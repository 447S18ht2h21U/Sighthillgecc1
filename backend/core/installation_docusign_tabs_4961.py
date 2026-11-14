"""Offline DocuSign recipient tab payload; NO provider operations.

This is a candidate configuration for later sandbox validation.
It is not a verified installed tab set or a signed inspection.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_docusign_placement_4960 import OfflineInspectionTabPlan
from .installation_docusign_contract_4959 import (
    UnsignedInstallationSigningContract,
    required_installation_signing_fields,
)
from .installation_inspection_form_4945 import INSPECTION_IDS


@dataclass(frozen=True)
class OfflineRecipientTabs:
    recipient_id: str
    document_id: str
    tabs: dict
    payload_sha256: str
    status: str = "OFFLINE_NOT_SUBMITTED"
    provider_validated: bool = False
    tabs_installed: bool = False
    envelope_created: bool = False
    signer_authenticated: bool = False
    findings_verified: bool = False
    completion_authorized: bool = False


def build_offline_recipient_tabs(*, contract, plan):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("DocuSign payload preview disabled.")
    if type(contract) is not UnsignedInstallationSigningContract:
        raise ValidationError("Unsigned signing contract required.")
    if type(plan) is not OfflineInspectionTabPlan:
        raise ValidationError("Verified offline placement plan required.")

    if (
        contract.status != "OFFLINE_SIGNING_CONTRACT_NOT_SENT"
        or contract.provider != "DOCUSIGN"
        or contract.envelope_id is not None
        or contract.provider_tabs_installed is not False
        or contract.provider_signature_verified is not False
        or contract.project_completion_authorized is not False
        or contract.fields != required_installation_signing_fields()
        or plan.status != "OFFLINE_POSITIONS_NOT_INSTALLED"
        or plan.provider_tabs_installed is not False
        or plan.envelope_created is not False
        or plan.provider_authenticated is not False
        or plan.completion_authorized is not False
        or plan.signing_contract_sha256 != contract.contract_sha256
        or plan.unsigned_pdf_sha256 != contract.unsigned_pdf_sha256
    ):
        raise ValidationError("Unsigned contract/placement mismatch.")

    positions = plan.radio_positions
    if len(positions) != 10:
        raise ValidationError("Ten inspection radio positions required.")

    groups = []
    for index, field_id in enumerate(INSPECTION_IDS):
        yes, no = positions[2 * index:2 * index + 2]
        if any(
            (
                position.field_id != field_id
                or position.choice != expected_choice
                or position.page_number != 1
                or position.width != 9
                or position.height != 9
                or position.x != expected_x
                or not 0 <= position.y <= 780
            )
            for position, expected_choice, expected_x in (
                (yes, "YES", 426),
                (no, "NO", 488),
            )
        ) or yes.y != no.y:
            raise ValidationError("Invalid or displaced manager answer tabs.")

        groups.append({
            "documentId": "1",
            "recipientId": "1",
            "groupName": field_id,
            "required": "true",
            "radios": [
                {
                    "pageNumber": "1",
                    "xPosition": str(pos.x),
                    "yPosition": str(pos.y),
                    "value": pos.choice,
                    "selected": "false",
                }
                for pos in (yes, no)
            ],
        })

    if (
        plan.signature_anchor != contract.fields[5].anchor
        or plan.date_signed_anchor != contract.fields[6].anchor
    ):
        raise ValidationError("Signature/date anchors changed.")

    tabs = {
        "radioGroupTabs": groups,
        "signHereTabs": [{
            "documentId": "1",
            "recipientId": "1",
            "anchorString": plan.signature_anchor,
            "anchorUnits": "pixels",
            "anchorXOffset": "0",
            "anchorYOffset": "0",
        }],
        "dateSignedTabs": [{
            "documentId": "1",
            "recipientId": "1",
            "anchorString": plan.date_signed_anchor,
            "anchorUnits": "pixels",
            "anchorXOffset": "0",
            "anchorYOffset": "0",
        }],
    }

    # An offline fingerprint detects changes to this candidate
    # configuration; it does not establish provider authenticity.
    canonical = json.dumps({
        "schema": "GECC_IM_DOCUSIGN_TABS_4961_V1",
        "contract_sha256": contract.contract_sha256,
        "plan_sha256": plan.plan_sha256,
        "tabs": tabs,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")

    return OfflineRecipientTabs(
        recipient_id="1",
        document_id="1",
        tabs=tabs,
        payload_sha256=sha256(canonical).hexdigest(),
    )
