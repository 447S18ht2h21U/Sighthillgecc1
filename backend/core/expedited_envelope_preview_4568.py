"""Development-only unified DocuSign envelope metadata preview.

No provider-ready envelope, authenticated send action, PDF transmission,
or installation authority is created by this module.
"""
from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role, User
from .expedited_recipient_binding_4567 import assess_unified_recipients
from .expedited_envelope_contract_4567 import FIELDS, DOCUMENTS
from .expedited_signing_remaining_layout_4567 import complete_visual_candidate
from .expedited_reviewer_choices_4567 import reviewer_choice_candidate
from .expedited_review_tabs_4568 import reviewer_provider_tabs_candidate


SENDER_ROLES = frozenset((Role.SALES_MANAGER, Role.CEO))
RECIPIENT_ROLES = ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER")

# Decision fields require mutually exclusive approve/reject controls and
# selected-choice initials. They cannot yet be encoded as provider tabs.
DECISION_FIELDS = frozenset((
    "expedited_manager_decision",
    "expedited_manager_initials",
    "expedited_manager_date",
    "expedited_comptroller_decision",
    "expedited_comptroller_initials",
    "expedited_comptroller_date",
))

TAB_TYPES = {
    "SIGNATURE": "signHereTabs",
    "INITIALS": "initialHereTabs",
    "DATE_SIGNED": "dateSignedTabs",
    "FULL_NAME": "fullNameTabs",
    "MULTILINE_TEXT": "textTabs",
    "DATE": "textTabs",
}


def build_unified_envelope_preview(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Unified DocuSign preview is development-only.")

    actor_id = getattr(actor, "pk", None)
    sender = User.objects.filter(pk=actor_id).first() if actor_id else None
    if (
        sender is None or sender.is_active is not True
        or sender.role not in SENDER_ROLES
    ):
        raise PermissionDenied("Only an active Sales Manager or CEO may release envelopes.")

    identity = assess_unified_recipients(
        actor=sender, project_id=project_id,
    )
    if (
        type(identity) is not dict
        or identity.get("send_authorized") is not False
        or identity.get("installation_authorized") is not False
        or identity.get("expedited_signer_authorized") is not False
        or identity.get("envelope_count") != 1
        or identity.get("documents") != ["CUSTOMER_SOW", "EXPEDITED_SERVICE"]
    ):
        raise ValidationError("Unified recipient binding failed closed.")

    recipients = identity.get("recipients")
    if (
        type(recipients) is not list or len(recipients) != 3
        or [item.get("role") for item in recipients] != list(RECIPIENT_ROLES)
        or [item.get("routing_order") for item in recipients] != [1, 2, 3]
        or [item.get("recipient_id") for item in recipients] != ["1", "2", "3"]
    ):
        raise ValidationError("Trusted recipient routing mismatch.")

    root = (
        Path(__file__).resolve().parents[2]
        / "docs/reference/GECC-20261107-final-seven"
    )
    layout = complete_visual_candidate(root)
    reviewer = reviewer_choice_candidate(root)

    definitions = {field[0]: field for field in FIELDS}
    if (
        len(FIELDS) != 17 or len(definitions) != 17
        or set(layout["tabs"]) != set(definitions)
        or DOCUMENTS != (("1", "CUSTOMER_SOW"), ("2", "EXPEDITED_SERVICE"))
        or set(reviewer["reviewer_controls"])
           != {"INSTALLATION_MANAGER", "COMPTROLLER"}
        or any(len(items) != 5 for items in reviewer["reviewer_controls"].values())
    ):
        raise ValidationError("Approved field or reviewer layout changed.")

    recipient_tabs = {
        name: {
            "signHereTabs": [],
            "initialHereTabs": [],
            "dateSignedTabs": [],
            "fullNameTabs": [],
            "textTabs": [],
        }
        for name in RECIPIENT_ROLES
    }

    for field_name, doc, field_type, owner, required in FIELDS:
        if field_name in DECISION_FIELDS:
            continue
        if field_type not in TAB_TYPES:
            raise ValidationError("Unsupported DocuSign field type.")
        placement = layout["tabs"][field_name]
        if placement["documentId"] != doc:
            raise ValidationError("Field and source-document identity differ.")

        tab = {
            key: placement[key]
            for key in (
                "documentId", "pageNumber",
                "xPosition", "yPosition", "width", "height",
            )
        }
        tab["tabLabel"] = field_name
        tab["required"] = "true" if required else "false"

        if field_type == "DATE":
            if owner != "PREPOPULATED":
                raise ValidationError("Proposed date is not a signing date.")
            # A prepopulated business date, not a signed-at timestamp.
            tab["value"] = identity["proposed_date"]
            tab["locked"] = "true"
            destination = "CUSTOMER"
        else:
            if owner not in RECIPIENT_ROLES:
                raise ValidationError("Unexpected signing field owner.")
            destination = owner
            if field_type == "DATE_SIGNED":
                # The DocuSign provider generates this date.
                # Do not accept or inject a user-entered value.
                if "value" in tab:
                    raise ValidationError("Date-signed tab cannot be prefilled.")

        recipient_tabs[destination][TAB_TYPES[field_type]].append(tab)

    planned_recipients = []
    for item in recipients:
        planned_recipients.append({
            "recipientId": item["recipient_id"],
            "routingOrder": str(item["routing_order"]),
            "role": item["role"],
            "name": item["name"],
            "email": item["email"],
            "tabs": recipient_tabs[item["role"]],
        })

    documents = []
    for doc_id, kind in DOCUMENTS:
        info = layout["documents"][kind]
        documents.append({
            "documentId": doc_id,
            "kind": kind,
            "name": info["filename"],
            "pdf_sha256": info["sha256"],
            "pages": info["pages"],
        })

    # Not a DocuSign API request. Deliberately omits documentBase64,
    # send status, provider credentials, and six unresolved reviewer
    # decision fields. This is only an internal construction preview.
    return {
        "status": "DEVELOPMENT_PREVIEW_NOT_SENDABLE",
        "project_id": identity["project_id"],
        "msr_id": identity["msr_id"],
        "msr_version": identity["msr_version"],
        "snapshot_sha256": identity["snapshot_sha256"],
        "proposed_date": identity["proposed_date"],
        "sender_user_id": str(sender.pk),
        "sender_role": sender.role,
        "documents": documents,
        "recipients": planned_recipients,
        "reviewer_controls": reviewer["reviewer_controls"],
        "conditional_reviewer_tab_candidate": reviewer_provider_tabs_candidate(),
        "reviewer_fields_pending": sorted(DECISION_FIELDS),
        "signature_dates_source": "DOCUSIGN_PROVIDER_ONLY",
        "customer_owned_signing": True,
        "shared_device_allowed_with_provider_authentication": True,
        "expedited_specific_authorization_verified": False,
        "reviewer_choices_provider_enforced": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
