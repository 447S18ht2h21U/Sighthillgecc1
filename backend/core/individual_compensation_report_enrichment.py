"""Limited, read-only evidence enrichment for individual compensation.

These functions do not grant access to compensation records.
Callers must obtain records through verified ownership scopes first.

No live API or existing report integration is provided here.
"""

from .individual_compensation_report_evidence_policy import (
    historical_msr_label,
    payment_evidence_label,
    project_association_label,
)


def _issued(record):
    """Determine whether related issuance evidence exists."""

    return hasattr(record, "payment_issuance")


def _contractor_settlement_verified(record):
    """Use the existence of independent settlement evidence."""

    return hasattr(record, "settlement_verification")


def enrich_owned_employee_payroll_record(record):
    """Return limited evidence for an already-authorized payroll record."""

    issuance = _issued(record)

    return {
        "project_association": "Not applicable to employee payroll",
        "historical_msr_attribution": historical_msr_label(False),
        "payment_evidence_status": payment_evidence_label(
            record.status,
            issuance,
            False,
            contractor=False,
        ),
        "payment_issued_at": (
            record.payment_issuance.issued_at.isoformat()
            if issuance
            else None
        ),
        "settlement_date": None,
        "settlement_independently_verified": False,
    }


def enrich_owned_contractor_payment_record(record):
    """Return limited evidence for an already-authorized contractor record."""

    issuance = _issued(record)
    verified = _contractor_settlement_verified(record)
    project = record.project if record.project_id else None

    return {
        "project_association": project_association_label(project is not None),
        "project_code": project.code if project is not None else None,
        "historical_msr_attribution": historical_msr_label(False),
        "payment_evidence_status": payment_evidence_label(
            record.status,
            issuance,
            verified,
            contractor=True,
        ),
        "payment_issued_at": (
            record.payment_issuance.issued_at.isoformat()
            if issuance
            else None
        ),
        "settlement_date": (
            record.settlement_verification.settlement_date.isoformat()
            if verified
            else None
        ),
        "settlement_independently_verified": verified,
    }