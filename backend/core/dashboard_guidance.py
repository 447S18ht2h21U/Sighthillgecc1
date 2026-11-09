"""Read-only, plain-language dashboard guidance.

This is advice, never authorization, evidence of completed work,
or permission to perform a protected operation.
"""

GUIDANCE = {
    "completed_customer_record": (
        "Review the MSR",
        "Check the submitted and approved MSR before preparing documents.",
    ),
    "contracted_for_work": (
        "Check signed agreement evidence",
        "A generated contract does not prove the customer signed it.",
    ),
    "invoice_signed": (
        "Check invoice evidence",
        "Do not treat a generated Invoice as a signed document.",
    ),
    "installation_scheduled": (
        "Check installation readiness",
        "Confirm payment, required waiting periods, equipment details, "
        "and assignment approvals before equipment pickup.",
    ),
    "installation_complete": (
        "Review verified completion evidence",
        "Check completion records and the applicable certificate.",
    ),
    "payment_received": (
        "Review verified payment records",
        "Confirm payment type, adjustments, and any remaining balance.",
    ),
}


def project_guidance(state, stage):
    """Return a hint only for an existing dashboard stage.

    The Dashboard API applies project visibility first. This function
    receives no user identity and has no database access.
    """
    if type(state) is not str:
        raise ValueError("Project state must be text.")
    if type(stage) is not str or stage not in GUIDANCE:
        raise ValueError("Unknown dashboard stage.")

    if state == "CANCELLED":
        label = "Review cancelled project"
        detail = "Confirm authorized reopening before further work."
    elif state == "SUBMITTED":
        label = "MSR review pending"
        detail = "An authorized reviewer must evaluate the submitted MSR."
    elif state == "REJECTED":
        label = "Correct rejected MSR"
        detail = "Review the rejection reason and prepare a corrected draft."
    elif state in ("DRAFT", "REVISED"):
        label = "Complete the draft MSR"
        detail = "Finish the draft and submit it for authorized review."
    elif state == "APPROVED":
        label, detail = GUIDANCE[stage]
    else:
        label = "Review project status"
        detail = "Confirm the current project state before taking action."

    return {
        "label": label,
        "detail": detail,
        "read_only": True,
    }
