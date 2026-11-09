"""Read-only personal payroll presentation adapter.

This module GRANTS NO PERMISSIONS. Never pass caller-supplied report
data to it as an authorization substitute.

The only supported database entry point below requires the existing
effective-permission gate and existing ownership-verified report.

No API registration, payment modification, or manager access.
"""
from .access_compensation_report_permissions import (
    permitted_own_compensation_report,
)


def _present_rows(records, *, employee):
    if not isinstance(records, list):
        raise ValueError("Authorized compensation records must be a list.")

    presented = []
    expected_type = "employee_payroll" if employee else "contractor_payment"
    amount_key = "net_amount" if employee else "final_amount"

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid compensation record.")
        if record.get("record_type") != expected_type:
            raise ValueError("Compensation record type mismatch.")
        if record.get("status") not in ("APPROVED", "PAID"):
            raise ValueError("Unapproved compensation cannot be presented.")

        evidence = record.get("payment_evidence")
        if not isinstance(evidence, dict):
            raise ValueError("Independent report enrichment is required.")

        amount = record.get(amount_key)
        if not isinstance(amount, str):
            raise ValueError("Expected an approved, formatted amount.")

        for field in ("period_start", "period_end", "kind", "status_label"):
            if not isinstance(record.get(field), str):
                raise ValueError("Missing verified compensation field.")

        evidence_status = evidence.get("payment_evidence_status")
        if not isinstance(evidence_status, str):
            raise ValueError("Missing payment evidence classification.")

        # Allowlist only. No account, tax, identity, or bank details.
        # Neither issuance nor settlement date is the same as paid_at.
        presented.append({
            "period_start": record["period_start"],
            "period_end": record["period_end"],
            "compensation_type": (
                "employee" if employee else "contractor"
            ),
            "kind": record["kind"],
            "amount": amount,
            "status": record["status"],
            "status_label": record["status_label"],
            "payment_evidence_status": evidence_status,
            "payment_issued_at": evidence.get("payment_issued_at"),
            "contractor_settlement_date": (
                evidence.get("settlement_date") if not employee else None
            ),
            "scheduled_payment_date": None,
            "actual_paid_date": None,
        })

    return presented


def present_authorized_personal_report(report):
    """Format an ALREADY AUTHORIZED own-compensation report only.

    This is not an authorization boundary or a public API.
    """
    if not isinstance(report, dict):
        raise ValueError("An authorized report is required.")
    if report.get("report_type") != "individual_compensation_period":
        raise ValueError("Unexpected compensation report.")
    if report.get("evidence_basis") != "ownership_verified_per_record":
        raise ValueError("Missing ownership-verified evidence basis.")
    if report.get("amount_basis") != "full_obligation_not_prorated":
        raise ValueError("Unexpected payroll amount basis.")

    return {
        "view": "my_compensation",
        "period_start": report["period_start"],
        "period_end": report["period_end"],
        "amount_basis": report["amount_basis"],
        "employee_records": _present_rows(
            report.get("employee_records"), employee=True
        ),
        "contractor_records": _present_rows(
            report.get("contractor_records"), employee=False
        ),
    }


def permitted_personal_payroll_presentation(actor, start_date, end_date):
    """Default-deny permission BEFORE ownership-scoped data retrieval."""
    authorized_report = permitted_own_compensation_report(
        actor, start_date, end_date
    )
    return present_authorized_personal_report(authorized_report)