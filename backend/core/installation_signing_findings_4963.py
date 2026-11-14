"""Parse candidate inspection selections without claiming DocuSign trust.

No signer identity, signature or signed date is accepted from this module.
Only a separately authenticated provider integration may establish them.
No database, envelope dispatch, work-order or completion operations.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_docusign_contract_4959 import (
    validate_five_findings,
)
from .installation_docusign_envelope_4962 import (
    OfflineInstallationEnvelope,
)
from .installation_inspection_form_4945 import (
    INSPECTION_IDS,
    INSPECTION_ITEMS,
)


HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class InspectionReviewCandidate:
    inspection_id: str
    question: str
    reason: str
    response: str | None


@dataclass(frozen=True)
class UnverifiedInspectionResponse:
    project_id: str
    approved_msr_id: str
    approved_msr_version: str
    signer_user_id: str
    envelope_package_sha256: str
    unsigned_pdf_sha256: str
    selections: tuple
    review_candidates: tuple[InspectionReviewCandidate, ...]
    response_sha256: str
    response_set_complete: bool
    status: str = "UNVERIFIED_LOCAL_RESPONSE_CANDIDATE"
    provider_response_authenticated: bool = False
    signer_authenticated: bool = False
    signature_verified: bool = False
    signed_date_verified: bool = False
    installation_verified: bool = False
    work_orders_created: bool = False
    receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def evaluate_inspection_response_candidate(*, envelope, selections):
    """Interpret raw radio choices. This NEVER authenticates their origin."""
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline response processing is disabled.")

    if type(envelope) is not OfflineInstallationEnvelope:
        raise ValidationError("Offline Installation envelope required.")
    if (
        envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.envelope_id is not None
        or envelope.provider_validated is not False
        or envelope.provider_tabs_installed is not False
        or envelope.provider_signed is not False
        or envelope.inspection_findings_verified is not False
        or envelope.completion_authorized is not False
        or type(envelope.envelope_package_sha256) is not str
        or not HEX64.fullmatch(envelope.envelope_package_sha256)
        or type(envelope.unsigned_pdf_sha256) is not str
        or not HEX64.fullmatch(envelope.unsigned_pdf_sha256)
    ):
        raise ValidationError("Envelope is not an unsubmitted local draft.")

    groups = (
        envelope.request.get("recipients", {})
        .get("signers", [])
    )
    if type(groups) is not list or len(groups) != 1:
        raise ValidationError("Exactly one intended manager signer required.")
    signer = groups[0]
    if type(signer) is not dict:
        raise ValidationError("Invalid signer configuration.")
    tabs = signer.get("tabs", {})
    if type(tabs) is not dict:
        raise ValidationError("Invalid signer tabs.")
    radio_groups = tabs.get("radioGroupTabs")
    if type(radio_groups) is not list or len(radio_groups) != 5:
        raise ValidationError("Five signing question groups required.")
    for index, group in enumerate(radio_groups):
        if (
            type(group) is not dict
            or group.get("groupName") != INSPECTION_IDS[index]
            or group.get("required") != "true"
            or type(group.get("radios")) is not list
            or len(group["radios"]) != 2
            or [r.get("value") for r in group["radios"]]
            != ["YES", "NO"]
        ):
            raise ValidationError("Signing question configuration changed.")

    if type(selections) is not dict or set(selections) != set(INSPECTION_IDS):
        raise ValidationError("Exactly five radio response groups required.")

    normalized = {}
    for key in INSPECTION_IDS:
        chosen = selections[key]
        # Represent each group's selected buttons as a list, so
        # contradictory Yes+No choices cannot be silently accepted.
        if type(chosen) is not list:
            raise ValidationError("Radio selections must be lists.")
        if len(chosen) > 1:
            raise ValidationError("Contradictory radio choices.")
        if len(chosen) == 0:
            normalized[key] = None
        elif type(chosen[0]) is str and chosen[0] in ("YES", "NO"):
            normalized[key] = chosen[0]
        else:
            raise ValidationError("Invalid radio selection.")

    complete = all(
        normalized[key] is not None for key in INSPECTION_IDS
    )
    if complete:
        validate_five_findings(normalized)

    reviews = []
    for key, question in zip(INSPECTION_IDS, INSPECTION_ITEMS):
        answer = normalized[key]
        if answer == "NO":
            reviews.append(InspectionReviewCandidate(
                key, question, "MANAGER_NEGATIVE_CANDIDATE", answer
            ))
        elif answer is None:
            reviews.append(InspectionReviewCandidate(
                key, question, "REQUIRED_RESPONSE_MISSING", None
            ))

    snapshot = tuple(
        (key, normalized[key]) for key in INSPECTION_IDS
    )
    payload = {
        "schema": "GECC_IM_UNVERIFIED_RESPONSES_4963_V1",
        "project_id": envelope.project_id,
        "msr_id": envelope.approved_msr_id,
        "msr_version": envelope.approved_msr_version,
        "signer_user_id": envelope.signer_user_id,
        "envelope_package_sha256": envelope.envelope_package_sha256,
        "unsigned_pdf_sha256": envelope.unsigned_pdf_sha256,
        "selections": snapshot,
        "review": [
            (item.inspection_id, item.reason)
            for item in reviews
        ],
    }
    digest = sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")).hexdigest()

    return UnverifiedInspectionResponse(
        project_id=envelope.project_id,
        approved_msr_id=envelope.approved_msr_id,
        approved_msr_version=envelope.approved_msr_version,
        signer_user_id=envelope.signer_user_id,
        envelope_package_sha256=envelope.envelope_package_sha256,
        unsigned_pdf_sha256=envelope.unsigned_pdf_sha256,
        selections=snapshot,
        review_candidates=tuple(reviews),
        response_sha256=digest,
        response_set_complete=complete,
    )
