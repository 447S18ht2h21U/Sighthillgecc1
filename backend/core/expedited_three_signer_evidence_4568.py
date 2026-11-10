
'''Structural three-signer DocuSign observation. NOT provider authentication.

The actual sandbox recipient-tabs response must be verified before
this candidate's metadata shape is accepted for operational use.
'''
from datetime import datetime
from uuid import UUID

from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .expedited_reviewer_choices_4567 import validate_review_choice
from .expedited_tab_contract_4568 import validate_offline_tab_contract

ROLES = ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER")
KINDS = (
    "signHereTabs", "initialHereTabs", "dateSignedTabs",
    "fullNameTabs", "textTabs",
)


def _instant(value):
    if type(value) is not str or not value:
        raise ValidationError("DocuSign timestamp missing.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError("Invalid DocuSign timestamp.") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValidationError("DocuSign timestamp must contain timezone.")
    return result


def _tabs(signer, category):
    tabs = signer.get("tabs")
    if type(tabs) is not dict or type(tabs.get(category)) is not list:
        raise ValidationError("Required DocuSign tab metadata missing.")
    return tabs[category]


def _lookup(signer, category, expected):
    matches = [
        tab for tab in _tabs(signer, category)
        if type(tab) is dict
        and tab.get("tabLabel") == expected["tabLabel"]
        and str(tab.get("documentId")) == expected["documentId"]
        and str(tab.get("pageNumber")) == expected["pageNumber"]
    ]
    if len(matches) != 1:
        raise ValidationError("Missing, duplicate, or misplaced signed tab.")
    return matches[0]


def validate_three_signer_observation(
    *, expected_envelope_id, offline_envelope, summary, recipients,
):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Three-signer evidence is not live-enabled.")

    validate_offline_tab_contract(offline_envelope)

    try:
        envelope_id = str(UUID(expected_envelope_id))
    except (TypeError, AttributeError, ValueError):
        raise ValidationError("Valid expected envelope ID required.") from None

    if expected_envelope_id != envelope_id:
        raise ValidationError("Noncanonical expected envelope ID.")

    if (
        type(summary) is not dict
        or summary.get("envelopeId") != envelope_id
        or summary.get("status") != "completed"
    ):
        raise ValidationError("Verified envelope completion metadata required.")

    completed_at = _instant(summary.get("completedDateTime"))
    if type(recipients) is not dict:
        raise ValidationError("Signer metadata missing.")

    signers = recipients.get("signers")
    planned = offline_envelope["recipients"]["signers"]
    if type(signers) is not list or len(signers) != 3:
        raise ValidationError("Three completed recipients required.")

    seen = set()
    times = []
    decisions = {}

    for index, (role, original) in enumerate(zip(ROLES, planned), 1):
        signer = signers[index - 1]

        if type(signer) is not dict:
            raise ValidationError("Signer metadata malformed.")

        recipient_id = str(index)
        email = signer.get("email")
        if (
            signer.get("recipientId") != recipient_id
            or str(signer.get("routingOrder")) != recipient_id
            or signer.get("name") != original["name"]
            or type(email) is not str
            or email.casefold() != original["email"].casefold()
            or signer.get("status") != "completed"
            or email.casefold() in seen
        ):
            raise ValidationError("Recipient identity, order, or completion differs.")

        seen.add(email.casefold())
        signed_at = _instant(signer.get("signedDateTime"))
        if signed_at > completed_at:
            raise ValidationError("Signing occurred after envelope completion.")
        times.append(signed_at)

        original_tabs = original["tabs"]
        for category in KINDS:
            for tab in original_tabs[category]:
                observed = _lookup(signer, category, tab)
                if category == "textTabs":
                    label = tab["tabLabel"]
                    if label in (
                        "sow_proposed_date", "expedited_requested_date"
                    ) and observed.get("value") != tab["value"]:
                        raise ValidationError("Signed proposed date differs.")
                    if (
                        label == "expedited_customer_reason"
                        and not str(observed.get("value", "")).strip()
                    ):
                        raise ValidationError("Customer's written reason missing.")

        if role == "CUSTOMER":
            continue

        group, = original_tabs["radioGroupTabs"]
        matches = [
            entry for entry in _tabs(signer, "radioGroupTabs")
            if type(entry) is dict
            and entry.get("groupName") == group["groupName"]
        ]
        if len(matches) != 1:
            raise ValidationError("Reviewer's decision group missing.")

        radios = matches[0].get("radios")
        if type(radios) is not list or len(radios) != 2:
            raise ValidationError("Reviewer's two decision options missing.")

        choices = {}
        for radio in radios:
            if type(radio) is not dict or radio.get("value") not in (
                "APPROVE", "REJECT"
            ):
                raise ValidationError("Unexpected reviewer decision value.")
            value = radio["value"]
            if value in choices or str(radio.get("selected")).lower() not in (
                "true", "false"
            ):
                raise ValidationError("Invalid or repeated decision selection.")
            choices[value] = str(radio["selected"]).lower() == "true"

        if set(choices) != {"APPROVE", "REJECT"}:
            raise ValidationError("Both decision alternatives required.")

        initials = {}
        for tab in original_tabs["initialHereTabs"]:
            if "conditionalParentValue" not in tab:
                continue
            observed = _lookup(signer, "initialHereTabs", tab)
            choice = tab["conditionalParentValue"]
            if (
                observed.get("conditionalParentLabel")
                    != tab["conditionalParentLabel"]
                or observed.get("conditionalParentValue") != choice
            ):
                raise ValidationError("Conditional initials binding differs.")
            initials[choice] = bool(str(observed.get("value", "")).strip())

        if set(initials) != {"APPROVE", "REJECT"}:
            raise ValidationError("Both conditional initials metadata required.")

        try:
            decision = validate_review_choice(
                approved=choices["APPROVE"],
                rejected=choices["REJECT"],
                approved_initialed=initials["APPROVE"],
                rejected_initialed=initials["REJECT"],
                signed_date=signed_at.date().isoformat(),
            )
        except ValueError:
            raise ValidationError("Reviewer decision/initials mismatch.") from None

        decisions[role] = decision["candidate_decision"]

    if times != sorted(times):
        raise ValidationError("Signing chronology violates recipient order.")

    # A structurally complete package is NOT an authorized installation.
    # Provider authenticity, actual signed tab semantics, retained PDF
    # fingerprints, certificate, and distribution remain separate gates.
    return {
        "status": "THREE_SIGNER_STRUCTURAL_CANDIDATE_ONLY",
        "envelope_id": envelope_id,
        "customer_signed_at": times[0].isoformat(),
        "manager_candidate_decision": decisions["INSTALLATION_MANAGER"],
        "comptroller_candidate_decision": decisions["COMPTROLLER"],
        "provider_authenticated": False,
        "reviewer_identity_verified": False,
        "signatures_verified": False,
        "signed_pdfs_retained": False,
        "certificate_retained": False,
        "distribution_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }
