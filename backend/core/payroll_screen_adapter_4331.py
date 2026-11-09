"""Test-only personal payroll screen data adapter.

The ONLY database-backed entry point uses the existing permission and
ownership-verified reporting service. The pure formatting function
must never be exposed as an authorization entry point.

No manager/company access, API registration, financial calculations,
database writes, or external custody trust claims are implemented.
"""
import re
from datetime import date

from .payroll_personal_presentation_4286 import (
    permitted_personal_payroll_presentation,
)

_AMOUNT = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}\Z")


def _date(value):
    if type(value) is not str:
        raise ValueError("Verified ISO date is required.")
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("Invalid ISO date.") from None
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical ISO date.")
    return parsed


def _rows(rows, *, expected_type, start, end):
    if type(rows) is not list or len(rows) > 1000:
        raise ValueError("Invalid authorized payroll collection.")

    result = []

    for row in rows:
        if type(row) is not dict:
            raise ValueError("Invalid authorized payroll row.")

        if row.get("compensation_type") != expected_type:
            raise ValueError("Unexpected compensation type.")

        status = row.get("status")
        if status not in ("APPROVED", "PAID"):
            raise ValueError("Draft or unknown payroll status.")

        label = row.get("status_label")
        expected_label = (
            "Paid" if status == "PAID"
            else "Approved - Not Yet Paid"
        )
        if label != expected_label:
            raise ValueError("Conflicting payroll status label.")

        amount = row.get("amount")
        if type(amount) is not str or _AMOUNT.fullmatch(amount) is None:
            raise ValueError("Expected exact two-decimal pay amount.")

        row_start = _date(row.get("period_start"))
        row_end = _date(row.get("period_end"))

        if row_start > row_end or row_end < start or row_start > end:
            raise ValueError("Payroll period does not overlap report.")

        kind = row.get("kind")
        if type(kind) is not str or not kind or len(kind) > 120:
            raise ValueError("Invalid compensation kind.")

        evidence = row.get("payment_evidence_status")
        if (
            type(evidence) is not str
            or not evidence
            or len(evidence) > 120
        ):
            raise ValueError("Missing payment evidence classification.")

        # Do not invent dates. Issuance/settlement are not actual paid dates.
        if (
            row.get("scheduled_payment_date") is not None
            or row.get("actual_paid_date") is not None
        ):
            raise ValueError("Unverified payroll dates cannot be displayed.")

        result.append({
            "period_start": row_start.isoformat(),
            "period_end": row_end.isoformat(),
            "compensation_type": expected_type,
            "kind": kind,
            "amount": amount,
            "status": status,
            "status_label": expected_label,
            "payment_evidence_status": evidence,
            "scheduled_payment_date": None,
            "actual_paid_date": None,
            "actual_paid_date_verified": False,
        })

    return result


def format_authorized_personal_screen_candidate(report):
    """Pure formatter for an ALREADY AUTHORIZED backend result only."""
    if type(report) is not dict:
        raise ValueError("Authorized payroll presentation required.")

    if report.get("view") != "my_compensation":
        raise ValueError("Unexpected payroll view.")

    if report.get("amount_basis") != "full_obligation_not_prorated":
        raise ValueError("Unexpected compensation amount basis.")

    start = _date(report.get("period_start"))
    end = _date(report.get("period_end"))

    if start > end:
        raise ValueError("Invalid report period.")

    employees = _rows(
        report.get("employee_records"),
        expected_type="employee",
        start=start,
        end=end,
    )
    contractors = _rows(
        report.get("contractor_records"),
        expected_type="contractor",
        start=start,
        end=end,
    )

    return {
        "view": "my_payroll_test_only",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "amount_basis": "full_obligation_not_prorated",
        "employee_records": employees,
        "contractor_records": contractors,
        "manager_or_company_scope_authorized": False,
        "payment_actions_authorized": False,
        "actual_paid_date_verified": False,
        "live_payroll_authorized": False,
    }


def candidate_personal_payroll_screen(actor, start_date, end_date):
    """Permission and ownership gate MUST run before formatting."""
    authorized = permitted_personal_payroll_presentation(
        actor, start_date, end_date
    )
    return format_authorized_personal_screen_candidate(authorized)


def payroll_screen_adapter_grants_live_access(*args, **kwargs):
    return False