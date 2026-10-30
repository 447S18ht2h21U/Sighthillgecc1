"""Nonbinding employee payroll-plan validation policy.

This module grants no permissions and performs no database writes.
A future integrated service must independently establish the correct
effective plan, authorized approver, payroll period, and audit trail.
"""

from datetime import date


def validate_payroll_plan(
    employee_id,
    plan_employee_id,
    plan_status,
    plan_effective_date,
    period_start,
    period_end,
    next_approved_effective_date=None,
):
    """Reject an unrelated, unapproved, or wrongly dated plan.

    The next approved effective date must be established from the
    authoritative compensation history by the calling service.
    A period spanning a change must be split or calculated in
    separately attributable segments before approval.
    """
    if (
        employee_id is None
        or plan_employee_id is None
        or employee_id != plan_employee_id
    ):
        raise ValueError(
            "Compensation plan does not belong to this employee."
        )

    if plan_status != "APPROVED":
        raise ValueError("An approved compensation plan is required.")

    for value in (plan_effective_date, period_start, period_end):
        if type(value) is not date:
            raise ValueError("Valid payroll and effective dates are required.")

    if period_start > period_end:
        raise ValueError("Payroll period dates are reversed.")

    if plan_effective_date > period_start:
        raise ValueError(
            "Compensation plan is not effective at the period start."
        )

    if next_approved_effective_date is not None:
        if type(next_approved_effective_date) is not date:
            raise ValueError("Invalid next compensation effective date.")

        if next_approved_effective_date <= plan_effective_date:
            raise ValueError("Compensation effective dates conflict.")

        if next_approved_effective_date <= period_start:
            raise ValueError(
                "A newer compensation plan already applies."
            )

        if next_approved_effective_date <= period_end:
            raise ValueError(
                "Payroll period spans a compensation change; split the calculation."
            )

    return True


def validate_compensation_approval_separation(
    approver_user_id,
    employee_user_id,
    requester_user_id,
):
    """Enforce separation of identities, not role authorization.

    Live implementation must separately verify the approver's
    currently active authority and resolve linked identities from
    the database, rather than trusting caller-supplied identifiers.
    """
    if approver_user_id is None or requester_user_id is None:
        raise ValueError("Approver and requester identities are required.")

    if approver_user_id == requester_user_id:
        raise ValueError("A requester cannot approve their own request.")

    if (
        employee_user_id is not None
        and approver_user_id == employee_user_id
    ):
        raise ValueError("An employee cannot approve their own compensation.")

    return True


def employee_compensation_policy_grants_access():
    """Policy validation never confers an application permission."""
    return False
