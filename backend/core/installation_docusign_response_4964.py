"""Untrusted DocuSign tab-response parser for the internal inspection.

Input may resemble a provider listTabs response, but the caller's data
is NOT authenticated. Genuine provider API retrieval, document digest,
envelope history, signer evidence, and retention are required separately.
No network calls, DB writes, or completion authorization.
"""

from dataclasses import dataclass
from hashlib import sha256
import base64
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_docusign_envelope_4962 import (
    OfflineInstallationEnvelope,
)
from .installation_signing_findings_4963 import (
    evaluate_inspection_response_candidate,
)
from .installation_inspection_form_4945 import INSPECTION_IDS


@dataclass(frozen=True)
class UnauthenticatedDocuSignObservation:
    project_id: str
    approved_msr_id: str
    signer_user_id: str
    envelope_package_sha256: str
    purported_envelope_id: str
    selections: tuple
    negative_inspection_ids: tuple
    observation_sha256: str
    status: str = "PROVIDER_SHAPED_RESPONSE_UNAUTHENTICATED"
    live_provider_retrieval_verified: bool = False
    envelope_identity_verified: bool = False
    signer_identity_verified: bool = False
    signed_document_verified: bool = False
    signed_date_verified: bool = False
    corrective_actions_created: bool = False
    receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def parse_untrusted_docusign_inspection_response(
    *, envelope, purported_envelope_id, recipient_tabs
):
    """Normalize all five radio answers; refuse incomplete/conflicting data."""
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline response observation disabled.")

    if type(envelope) is not OfflineInstallationEnvelope:
        raise ValidationError("Expected offline envelope package.")
    if (
        envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.envelope_id is not None
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
    ):
        raise ValidationError("Offline envelope unexpectedly authorized.")

    if (
        type(purported_envelope_id) is not str
        or not purported_envelope_id.strip()
        or purported_envelope_id != purported_envelope_id.strip()
        or len(purported_envelope_id) > 128
    ):
        raise ValidationError("Purported envelope reference required.")

    # Independently check that the unsigned document in the local package
    # still matches the original contract's PDF fingerprint.
    try:
        documents = envelope.request["documents"]
        signers = envelope.request["recipients"]["signers"]
        if (
            type(documents) is not list or len(documents) != 1
            or type(signers) is not list or len(signers) != 1
            or type(documents[0]) is not dict
            or type(signers[0]) is not dict
        ):
            raise ValueError("Local package shape changed.")
        pdf = base64.b64decode(
            documents[0]["documentBase64"], validate=True
        )
        if sha256(pdf).hexdigest() != envelope.unsigned_pdf_sha256:
            raise ValueError("Unsigned PDF fingerprint mismatch.")
        intended_tabs = signers[0]["tabs"]
        expected_groups = intended_tabs["radioGroupTabs"]
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ValidationError("Local package integrity invalid.") from exc

    if (
        type(expected_groups) is not list
        or len(expected_groups) != 5
        or type(recipient_tabs) is not dict
        or set(recipient_tabs) != {"radioGroupTabs"}
        or type(recipient_tabs["radioGroupTabs"]) is not list
        or len(recipient_tabs["radioGroupTabs"]) != 5
    ):
        raise ValidationError("Exactly five response groups required.")

    selections = {}
    returned = recipient_tabs["radioGroupTabs"]
    for index, field_id in enumerate(INSPECTION_IDS):
        expected = expected_groups[index]
        matches = [
            group for group in returned
            if type(group) is dict
            and group.get("groupName") == field_id
        ]
        if (
            type(expected) is not dict
            or expected.get("groupName") != field_id
            or expected.get("required") != "true"
            or len(matches) != 1
        ):
            raise ValidationError("Question identity mismatch.")

        group = matches[0]
        if set(group) != {"groupName", "radios"}:
            raise ValidationError("Unexpected response group fields.")
        radios = group["radios"]
        if (
            type(radios) is not list
            or len(radios) != 2
            or any(type(radio) is not dict for radio in radios)
            or [radio.get("value") for radio in radios]
            != ["YES", "NO"]
            or any(set(radio) != {"value", "selected"} for radio in radios)
        ):
            raise ValidationError("Malformed radio response.")
        selected = [
            radio["value"] for radio in radios
            if radio["selected"] == "true"
        ]
        if any(
            radio["selected"] not in ("true", "false")
            or type(radio["selected"]) is not str
            for radio in radios
        ) or len(selected) != 1:
            raise ValidationError("Each required question needs one answer.")
        selections[field_id] = selected

    result = evaluate_inspection_response_candidate(
        envelope=envelope, selections=selections
    )
    if (
        result.response_set_complete is not True
        or result.provider_response_authenticated is not False
        or result.completion_authorized is not False
    ):
        raise ValidationError("Response candidate incorrectly trusted.")

    negatives = tuple(
        key for key, value in result.selections if value == "NO"
    )
    material = {
        "schema": "GECC_UNAUTHENTICATED_DOCUSIGN_TABS_4964_V1",
        "project_id": envelope.project_id,
        "msr_id": envelope.approved_msr_id,
        "signer_user_id": envelope.signer_user_id,
        "package_sha256": envelope.envelope_package_sha256,
        "purported_envelope_id": purported_envelope_id,
        "answers": result.selections,
    }
    digest = sha256(json.dumps(
        material, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()

    return UnauthenticatedDocuSignObservation(
        project_id=envelope.project_id,
        approved_msr_id=envelope.approved_msr_id,
        signer_user_id=envelope.signer_user_id,
        envelope_package_sha256=envelope.envelope_package_sha256,
        purported_envelope_id=purported_envelope_id,
        selections=result.selections,
        negative_inspection_ids=negatives,
        observation_sha256=digest,
    )
