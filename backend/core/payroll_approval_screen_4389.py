"""VERIDIAN 1907P-4389: synthetic Approvals presentation adapter.

Test-only formatting of fictional records, reusing the 4388 policy.
No models, queries, network calls, authority grants, approvals or payments.
Caller-supplied audit references are NOT verified database evidence.
This module must never be registered as an operational API.
"""

import re

from payroll_approval_evidence_4388 import (
    validate_fictional_approval_evidence_4388,
)

_REFERENCE = re.compile(r"TEST-[A-Z0-9-]{1,30}\Z")
_RECIPIENT = re.compile(r"Fictional [A-Za-z ]{1,60}\Z")
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]{0,11})\.[0-9]{2}\Z")


def format_fictional_approval_screen_4389(source):
    """Format previously proposed fictional approval data only."""
    if type(source) is not dict:
        raise ValueError("Fictional approval collection required.")

    if source.get("view") != "fictional_approvals_review_only":
        raise ValueError("Only fictional review is permitted.")

    for flag in (
        "manager_authority_verified",
        "comptroller_authority_verified",
        "live_approval_authorized",
        "payment_actions_authorized",
        "actual_paid_date_verified",
    ):
        if source.get(flag) is not False:
            raise ValueError("Operational authority claims prohibited.")

    rows = source.get("rows")
    if type(rows) is not list or len(rows) > 100:
        raise ValueError("Invalid fictional approval collection.")

    result = []
    seen = set()

    for row in rows:
        if type(row) is not dict:
            raise ValueError("Fictional approval row required.")

        reference = row.get("reference")
        recipient = row.get("recipient")
        amount = row.get("amount")

        if (
            type(reference) is not str
            or _REFERENCE.fullmatch(reference) is None
            or reference in seen
        ):
            raise ValueError("Invalid or duplicate fictional reference.")

        if (
            type(recipient) is not str
            or _RECIPIENT.fullmatch(recipient) is None
        ):
            raise ValueError("Only fictional recipients permitted.")

        if type(amount) is not str or _AMOUNT.fullmatch(amount) is None:
            raise ValueError("Invalid exact compensation amount.")

        if int(amount.replace(".", "")) > 9007199254740991:
            raise ValueError("Amount exceeds safe presentation range.")

        if row.get("actual_paid_date_verified") is not False:
            raise ValueError("Payment date verification not permitted.")

        if row.get("actual_paid_date") is not None:
            raise ValueError("Actual payment date prohibited.")

        validated = validate_fictional_approval_evidence_4388({
            **row,
            "view": source["view"],
            "manager_authority_verified": False,
            "comptroller_authority_verified": False,
            "live_approval_authorized": False,
            "payment_actions_authorized": False,
            "actual_paid_date_verified": False,
        })

        stage = validated["stage"]
        audit = row.get("audit_evidence")

        if audit != (
            "RECORDED" if stage == "APPROVED" else "PENDING"
        ):
            raise ValueError("Conflicting fictional audit stage.")

        seen.add(reference)

        result.append({
            "reference": reference,
            "recipient": recipient,
            "workstream": validated["workstream"],
            "amount": amount,
            "requester_id": row["requester_id"],
            "first_approver_id": row["first_approver_id"],
            "final_approver_id": row["final_approver_id"],
            "stage": stage,
            "audit_evidence": audit,
            "actual_paid_date": None,
            "actual_paid_date_verified": False,
        })

    return {
        "view": "fictional_approvals_review_only",
        "manager_authority_verified": False,
        "comptroller_authority_verified": False,
        "live_approval_authorized": False,
        "payment_actions_authorized": False,
        "actual_paid_date_verified": False,
        "rows": result,
    }


def approval_screen_4389_grants_live_access():
    return False
