"""VERIDIAN 4413: APPROVED corporate financial approval policy.

Comptroller creates; a different CEO gives final approval.
An approved report requires durable audit evidence and immutable
historical snapshot protection.

Pure policy component: NOT registered with Django, its API,
the database, or the operational approval service.
"""

import hashlib
import json
import re

_ID = re.compile(r"TEST-[A-Z0-9-]{1,36}\Z")


def _identity(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("Synthetic actor identity required.")
    return value


def fingerprint_draft_4413(snapshot):
    if type(snapshot) is not dict or not snapshot:
        raise ValueError("Nonempty financial snapshot required.")
    try:
        canonical = json.dumps(
            snapshot, sort_keys=True, separators=(",", ":"),
            allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("Invalid financial snapshot.") from None
    return hashlib.sha256(canonical).hexdigest()


def evaluate_financial_approval_4413(request):
    """Check required policy conditions without approving anything."""
    if type(request) is not dict:
        raise ValueError("Structured approval review required.")

    if request.get("creator_role") != "COMPTROLLER":
        raise ValueError("Only the Comptroller prepares the report.")

    if request.get("approver_role") != "CEO":
        raise ValueError("Only the CEO may provide final approval.")

    creator = _identity(request.get("creator_id"))
    approver = _identity(request.get("approver_id"))
    if creator == approver:
        raise ValueError("Financial self-approval is prohibited.")

    if request.get("report_status") != "DRAFT":
        raise ValueError("Only a draft report may be approved.")

    if request.get("accounting_reconciled") is not True:
        raise ValueError("Accounting review is incomplete.")

    if request.get("evidence_verified") is not True:
        raise ValueError("Independent supporting evidence required.")

    snapshot_hash = fingerprint_draft_4413(
        request.get("report_snapshot")
    )

    return {
        "policy": "COMPTROLLER_PREPARES_CEO_APPROVES",
        "creator_id": creator,
        "approver_id": approver,
        "snapshot_sha256": snapshot_hash,
        "policy_conditions_satisfied": True,
        "durable_audit_written": False,
        "database_immutability_verified": False,
        "operational_approval_performed": False,
    }


def approval_policy_grants_live_access_4413():
    return False
