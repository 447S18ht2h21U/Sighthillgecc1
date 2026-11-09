"""VERIDIAN Step 1907P-4388: synthetic approval evidence policy.

Pure, isolated validation only. NOT an authorization service.
No database access, record mutations, API registration or payments.
Never treat caller-supplied identities or audit labels as verified.
Existing CEO approval services remain unchanged.
"""

import re

_TEST_ID = re.compile(r"TEST-[A-Z0-9-]{1,30}\Z")

_MANAGER = {
    "SALES": "SALES_MANAGER",
    "INSTALLATION": "INSTALLATION_MANAGER",
}


def _synthetic_id(value):
    if type(value) is not str or _TEST_ID.fullmatch(value) is None:
        raise ValueError("Synthetic TEST identifier required.")
    return value


def validate_fictional_approval_evidence_4388(candidate):
    """Validate proposed two-person states; never grant authority."""
    if type(candidate) is not dict:
        raise ValueError("Fictional approval evidence required.")

    if candidate.get("view") != "fictional_approvals_review_only":
        raise ValueError("Only fictional approval review is permitted.")

    for key in (
        "manager_authority_verified",
        "comptroller_authority_verified",
        "live_approval_authorized",
        "payment_actions_authorized",
        "actual_paid_date_verified",
    ):
        if candidate.get(key) is not False:
            raise ValueError("Operational authority is prohibited.")

    if candidate.get("actual_paid_date") is not None:
        raise ValueError("Actual payment dates are prohibited.")

    workstream = candidate.get("workstream")
    if workstream not in _MANAGER:
        raise ValueError("Invalid compensation workstream.")

    stage = candidate.get("stage")
    if stage not in (
        "WAITING_MANAGER",
        "WAITING_COMPTROLLER",
        "APPROVED",
    ):
        raise ValueError("Invalid approval stage.")

    requester = _synthetic_id(candidate.get("requester_id"))
    recipient = _synthetic_id(candidate.get("recipient_id"))

    manager_id = candidate.get("first_approver_id")
    final_id = candidate.get("final_approver_id")
    manager_role = candidate.get("first_approver_role")
    final_role = candidate.get("final_approver_role")
    manager_audit = candidate.get("first_audit_reference")
    final_audit = candidate.get("final_audit_reference")

    if stage == "WAITING_MANAGER":
        if any(value is not None for value in (
            manager_id, final_id, manager_role, final_role,
            manager_audit, final_audit,
        )):
            raise ValueError("Manager-pending evidence must be empty.")

    else:
        manager_id = _synthetic_id(manager_id)
        manager_audit = _synthetic_id(manager_audit)

        if manager_role != _MANAGER[workstream]:
            raise ValueError("Wrong first-approver workstream.")

        if manager_id in (requester, recipient):
            raise ValueError("Manager self-approval prohibited.")

        if stage == "WAITING_COMPTROLLER":
            if any(value is not None for value in (
                final_id, final_role, final_audit,
            )):
                raise ValueError("Final approval must remain pending.")

        else:
            final_id = _synthetic_id(final_id)
            final_audit = _synthetic_id(final_audit)

            if final_role != "COMPTROLLER":
                raise ValueError("Final approver must be Comptroller.")

            if final_id in (requester, recipient, manager_id):
                raise ValueError("Self-approval or duplicate approver.")

            if final_audit == manager_audit:
                raise ValueError("Approval audit evidence must differ.")

    return {
        "view": "fictional_approvals_review_only",
        "workstream": workstream,
        "stage": stage,
        "managerAuthorityVerified": False,
        "comptrollerAuthorityVerified": False,
        "liveApprovalAuthorized": False,
        "paymentActionsAvailable": False,
        "actualPaidDate": None,
        "evidenceShapeValidated": True,
    }


def approval_evidence_4388_grants_live_access():
    return False
