
import base64
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .expedited_envelope_contract_4567 import DOCUMENTS
from .expedited_envelope_preview_4568 import build_unified_envelope_preview
from .expedited_review_tabs_4568 import reviewer_provider_tabs_candidate

REFERENCE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "docs/reference/GECC-20261107-final-seven"
)
ROLES = ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER")
TAB_TYPES = {
    "signHereTabs", "initialHereTabs", "dateSignedTabs",
    "fullNameTabs", "textTabs",
}


def assemble_offline_candidate(*, preview, reference_root=REFERENCE_ROOT):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline signing assembly is development-only.")

    if type(preview) is not dict or (
        preview.get("status") != "DEVELOPMENT_PREVIEW_NOT_SENDABLE"
        or preview.get("sender_role") not in ("CEO", "SALES_MANAGER")
        or preview.get("send_authorized") is not False
        or preview.get("installation_authorized") is not False
        or preview.get("expedited_specific_authorization_verified") is not False
        or preview.get("reviewer_choices_provider_enforced") is not False
        or preview.get("signature_dates_source") != "DOCUSIGN_PROVIDER_ONLY"
    ):
        raise ValidationError("Protected offline preview required.")

    recipients = deepcopy(preview.get("recipients"))
    documents = preview.get("documents")

    if (
        type(recipients) is not list or len(recipients) != 3
        or type(documents) is not list or len(documents) != 2
        or tuple((d.get("documentId"), d.get("kind")) for d in documents)
            != DOCUMENTS
        or tuple(r.get("role") for r in recipients) != ROLES
        or [r.get("recipientId") for r in recipients] != ["1", "2", "3"]
        or [r.get("routingOrder") for r in recipients] != ["1", "2", "3"]
    ):
        raise ValidationError("Document or signer routing mismatch.")

    emails = [str(r.get("email", "")).strip().casefold() for r in recipients]
    if (
        len(set(emails)) != 3
        or any("@" not in email or any(c.isspace() for c in email)
               for email in emails)
        or any(not str(r.get("name", "")).strip() for r in recipients)
    ):
        raise ValidationError("Three distinct signer identities required.")

    sources = []
    for document in documents:
        name = document.get("name")
        fingerprint = document.get("pdf_sha256")
        if (
            type(name) is not str or not name
            or "/" in name or chr(92) in name or name in (".", "..")
            or type(fingerprint) is not str or len(fingerprint) != 64
        ):
            raise ValidationError("Approved PDF reference invalid.")

        path = Path(reference_root) / name
        content = path.read_bytes() if path.is_file() else b""
        if (
            not content.startswith(b"%PDF-")
            or sha256(content).hexdigest().upper() != fingerprint.upper()
        ):
            raise ValidationError("Approved PDF fingerprint mismatch.")

        sources.append({
            "documentId": document["documentId"],
            "name": name,
            "fileExtension": "pdf",
            "transformPdfFields": "false",
            "documentBase64": base64.b64encode(content).decode("ascii"),
        })

    for recipient in recipients:
        tabs = recipient.get("tabs")
        if type(tabs) is not dict or set(tabs) != TAB_TYPES:
            raise ValidationError("Signer tab coverage differs.")
        for tab_type, items in tabs.items():
            if type(items) is not list:
                raise ValidationError("Invalid signer tab collection.")
            for tab in items:
                if (
                    type(tab) is not dict
                    or tab.get("documentId") not in ("1", "2")
                    or tab.get("pageNumber") not in ("1", "2")
                    or not tab.get("tabLabel")
                ):
                    raise ValidationError("Invalid signing tab.")
                if tab_type == "dateSignedTabs" and "value" in tab:
                    raise ValidationError("DocuSign signing date was prefilled.")

    choices = reviewer_provider_tabs_candidate()
    if (
        choices.get("provider_behavior_verified") is not False
        or choices.get("send_authorized") is not False
        or choices.get("installation_authorized") is not False
    ):
        raise ValidationError("Reviewer controls prematurely activated.")

    for role, recipient_id in (
        ("INSTALLATION_MANAGER", "2"),
        ("COMPTROLLER", "3"),
    ):
        entry = choices["reviewers"][role]
        if entry.get("recipientId") != recipient_id:
            raise ValidationError("Reviewer recipient mismatch.")
        groups = entry["radioGroupTabs"]
        if len(groups) != 1 or len(groups[0].get("radios", [])) != 2:
            raise ValidationError("Reviewer decision coverage differs.")

        target = recipients[int(recipient_id) - 1]["tabs"]
        target["radioGroupTabs"] = deepcopy(groups)
        target["initialHereTabs"].extend(
            deepcopy(entry["initialHereTabs"])
        )
        target["dateSignedTabs"].extend(
            deepcopy(entry["dateSignedTabs"])
        )

    candidate = {
        "status": "UNSENDABLE_OFFLINE_CANDIDATE",
        "source_msr_id": preview["msr_id"],
        "source_snapshot_sha256": preview["snapshot_sha256"],
        "documents": sources,
        "recipients": {"signers": recipients},
        "provider_conditional_behavior_verified": False,
        "expedited_signer_authorized": False,
        "send_authorized": False,
        "installation_authorized": False,
    }

    # Mandatory independent structural gate. Never return the candidate
    # if any required DocuSign field or reviewer condition is missing.
    from .expedited_tab_contract_4568 import validate_offline_tab_contract
    checked = validate_offline_tab_contract(candidate)
    if (
        type(checked) is not dict
        or checked.get("status") != "OFFLINE_TAB_CONTRACT_VALIDATED"
        or checked.get("provider_behavior_verified") is not False
        or checked.get("send_authorized") is not False
        or checked.get("installation_authorized") is not False
    ):
        raise ValidationError("Mandatory offline contract check failed.")
    return candidate


def build_offline_for_project(*, actor, project_id):
    return assemble_offline_candidate(
        preview=build_unified_envelope_preview(
            actor=actor, project_id=project_id
        )
    )
