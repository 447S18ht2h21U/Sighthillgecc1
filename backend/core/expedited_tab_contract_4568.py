
'''Strict provider-field contract checks for the unsendable envelope.

This validator confirms local structure only. It does not claim
DocuSign sandbox behavior, signature verification, or send authority.
'''
from django.core.exceptions import ValidationError
from .expedited_envelope_contract_4567 import FIELDS

ROLES = ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER")
TYPES = {
    "SIGNATURE": "signHereTabs",
    "INITIALS": "initialHereTabs",
    "DATE_SIGNED": "dateSignedTabs",
    "FULL_NAME": "fullNameTabs",
    "MULTILINE_TEXT": "textTabs",
    "DATE": "textTabs",
}
DECISIONS = {
    "expedited_manager_decision", "expedited_manager_initials",
    "expedited_manager_date", "expedited_comptroller_decision",
    "expedited_comptroller_initials", "expedited_comptroller_date",
}


def validate_offline_tab_contract(envelope):
    if (
        type(envelope) is not dict
        or envelope.get("status") != "UNSENDABLE_OFFLINE_CANDIDATE"
        or envelope.get("send_authorized") is not False
        or envelope.get("installation_authorized") is not False
        or envelope.get("provider_conditional_behavior_verified") is not False
    ):
        raise ValidationError("Provider contract requires disabled offline candidate.")

    recipients = envelope.get("recipients", {}).get("signers")
    if type(recipients) is not list or len(recipients) != 3:
        raise ValidationError("Three signer recipients required.")

    if (
        tuple(r.get("role") for r in recipients) != ROLES
        or [r.get("recipientId") for r in recipients] != ["1", "2", "3"]
        or [r.get("routingOrder") for r in recipients] != ["1", "2", "3"]
    ):
        raise ValidationError("Recipient identities or signing order differ.")

    expected = {
        role: set() for role in ROLES
    }
    for field, document, kind, owner, required in FIELDS:
        if field in DECISIONS:
            continue
        if kind not in TYPES:
            raise ValidationError("Unsupported field requirement.")
        destination = "CUSTOMER" if owner == "PREPOPULATED" else owner
        expected[destination].add((TYPES[kind], field, document))

    required_labels = set()
    observed_labels = set()

    for recipient in recipients:
        role = recipient["role"]
        tabs = recipient.get("tabs")
        if type(tabs) is not dict:
            raise ValidationError("Missing recipient tabs.")

        for category in (
            "signHereTabs", "initialHereTabs",
            "dateSignedTabs", "fullNameTabs", "textTabs"
        ):
            items = tabs.get(category)
            if type(items) is not list:
                raise ValidationError("Missing signer tab category.")

            for tab in items:
                if type(tab) is not dict:
                    raise ValidationError("Malformed signer tab.")
                label = tab.get("tabLabel")
                if type(label) is not str or not label:
                    raise ValidationError("Unnamed signer tab.")

                for key in (
                    "documentId", "pageNumber", "xPosition", "yPosition"
                ):
                    if type(tab.get(key)) is not str:
                        raise ValidationError("Signing placement must be explicit.")

                if tab["documentId"] not in ("1", "2"):
                    raise ValidationError("Unknown document ID.")

                page = int(tab["pageNumber"])
                if not 1 <= page <= (2 if tab["documentId"] == "1" else 1):
                    raise ValidationError("Signing page mismatch.")

                if category in (
                    "signHereTabs", "initialHereTabs",
                    "dateSignedTabs", "fullNameTabs"
                ) and "value" in tab:
                    raise ValidationError(
                        "DocuSign signing data cannot be prepopulated."
                    )

                if category == "textTabs" and label in (
                    "sow_proposed_date", "expedited_requested_date"
                ):
                    if (
                        tab.get("locked") != "true"
                        or tab.get("value") is None
                    ):
                        raise ValidationError("Proposed business date not locked.")

                identity = (category, label, tab["documentId"])
                if identity in expected[role]:
                    if identity in observed_labels:
                        raise ValidationError("Duplicate required signer field.")
                    observed_labels.add(identity)
                    required_labels.add(identity)
                elif not (
                    role in ("INSTALLATION_MANAGER", "COMPTROLLER")
                    and category in ("initialHereTabs", "dateSignedTabs")
                    and label.startswith(role.lower() + "-")
                ):
                    raise ValidationError("Unexpected signing field.")

    expected_flat = set().union(*expected.values())
    if required_labels != expected_flat:
        raise ValidationError("Required signing fields missing.")

    for role, recipient in zip(ROLES[1:], recipients[1:]):
        tabs = recipient["tabs"]
        groups = tabs.get("radioGroupTabs")
        if type(groups) is not list or len(groups) != 1:
            raise ValidationError("Each reviewer needs one exclusive decision.")

        group = groups[0]
        group_name = role.lower() + "-expedited-decision"
        radios = group.get("radios")
        if (
            group.get("groupName") != group_name
            or group.get("required") != "true"
            or group.get("documentId") != "2"
            or type(radios) is not list or len(radios) != 2
            or {r.get("value") for r in radios} != {"APPROVE", "REJECT"}
            or any(r.get("selected") != "false" for r in radios)
        ):
            raise ValidationError("Reviewer single-choice rule invalid.")

        initials = [
            t for t in tabs["initialHereTabs"]
            if t["tabLabel"].startswith(role.lower() + "-")
        ]
        if (
            len(initials) != 2
            or {t.get("conditionalParentValue") for t in initials}
                != {"APPROVE", "REJECT"}
            or any(
                t.get("conditionalParentLabel") != group_name
                or t.get("optional") != "false"
                or t["documentId"] != "2"
                for t in initials
            )
        ):
            raise ValidationError("Selected-choice initials not enforced.")

        dates = [
            t for t in tabs["dateSignedTabs"]
            if t["tabLabel"] == role.lower() + "-expedited-date-signed"
        ]
        if len(dates) != 1 or "value" in dates[0]:
            raise ValidationError("DocuSign reviewer signed date required.")

    customer = recipients[0]
    if customer["tabs"].get("radioGroupTabs"):
        raise ValidationError("Customer cannot execute reviewer decision.")

    return {
        "status": "OFFLINE_TAB_CONTRACT_VALIDATED",
        "primary_field_count": 11,
        "reviewer_decision_groups": 2,
        "reviewer_conditional_initials": 4,
        "provider_behavior_verified": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
