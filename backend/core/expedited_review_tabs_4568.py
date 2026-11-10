"""Unsendable DocuSign conditional-reviewer tab candidates.

The provider must independently confirm the radio choice, selected
initials, and signed date. Candidate tabs never constitute approval.
"""
from django.core.exceptions import ValidationError

from .expedited_reviewer_choices_4567 import REVIEW_REGIONS

REVIEWER_IDS = {
    "INSTALLATION_MANAGER": "2",
    "COMPTROLLER": "3",
}
EXPECTED_KEYS = {
    "approve", "reject", "approve_initials", "reject_initials", "date",
}


def reviewer_provider_tabs_candidate():
    if set(REVIEW_REGIONS) != set(REVIEWER_IDS):
        raise ValidationError("Reviewer roles changed.")

    result = {}
    for role, recipient_id in REVIEWER_IDS.items():
        regions = REVIEW_REGIONS[role]
        if set(regions) != EXPECTED_KEYS:
            raise ValidationError("Reviewer control coverage changed.")

        def position(key):
            x, y, width, height = regions[key]
            if (
                any(type(v) is not int for v in (x, y, width, height))
                or x < 0 or y < 0
                or width <= 0 or height <= 0
                or x + width > 612 or y + height > 792
            ):
                raise ValidationError("Reviewer field outside approved PDF.")
            return {
                "documentId": "2", "pageNumber": "1",
                "xPosition": str(x), "yPosition": str(y),
            }

        group_name = role.lower() + "-expedited-decision"
        radios = []
        initials = []
        for decision, choice_key, initial_key in (
            ("APPROVE", "approve", "approve_initials"),
            ("REJECT", "reject", "reject_initials"),
        ):
            radio = {
                **position(choice_key),
                "value": decision,
                "selected": "false",
                "required": "true",
            }
            radios.append(radio)
            initials.append({
                **position(initial_key),
                "tabLabel": role.lower() + "-" + decision.lower() + "-initials",
                "optional": "false",
                "conditionalParentLabel": group_name,
                "conditionalParentValue": decision,
            })

        result[role] = {
            "recipientId": recipient_id,
            "radioGroupTabs": [{
                "groupName": group_name,
                "documentId": "2",
                "required": "true",
                "radios": radios,
            }],
            "initialHereTabs": initials,
            "dateSignedTabs": [{
                **position("date"),
                "tabLabel": role.lower() + "-expedited-date-signed",
            }],
        }

    if result["INSTALLATION_MANAGER"]["recipientId"] == (
        result["COMPTROLLER"]["recipientId"]
    ):
        raise ValidationError("Reviewer recipients are not independent.")

    return {
        "status": "PROVIDER_CONDITIONAL_TAB_CANDIDATE_ONLY",
        "reviewers": result,
        "exactly_one_choice_required": True,
        "selected_choice_initials_required": True,
        "date_signed_source": "DOCUSIGN_PROVIDER_ONLY",
        "provider_behavior_verified": False,
        "send_authorized": False,
        "installation_authorized": False,
    }
