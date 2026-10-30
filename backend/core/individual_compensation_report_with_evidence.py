"""Ownership-safe individual compensation report with evidence.

This service builds on the existing restricted individual report.
Each enrichment lookup independently checks record ownership.

No API endpoint, financial mutation, or administrative access
is created by this module.
"""

from .individual_compensation_report_services import (
    own_individual_compensation_period_report,
)
from .individual_compensation_report_authorized_enrichment import (
    authorized_contractor_payment_enrichment,
    authorized_employee_payroll_enrichment,
)


def own_individual_compensation_report_with_evidence(
    actor,
    start_date,
    end_date,
):
    """Return the actor's approved/paid compensation with limited evidence."""

    report = own_individual_compensation_period_report(
        actor,
        start_date,
        end_date,
    )

    employee_rows = []

    for row in report["employee_records"]:
        evidence = authorized_employee_payroll_enrichment(
            actor,
            row["record_id"],
        )
        employee_rows.append({
            **row,
            "payment_evidence": evidence,
        })

    contractor_rows = []

    for row in report["contractor_records"]:
        evidence = authorized_contractor_payment_enrichment(
            actor,
            row["record_id"],
        )
        contractor_rows.append({
            **row,
            "payment_evidence": evidence,
        })

    return {
        **report,
        "employee_records": employee_rows,
        "contractor_records": contractor_rows,
        "evidence_basis": "ownership_verified_per_record",
    }