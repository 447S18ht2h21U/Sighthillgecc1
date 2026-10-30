"""Minimal read-only self-service compensation disclosure.

Do not use this module for payroll approvals, payment issuance,
administrative reporting, or authorization to edit financial records.

The caller must separately enforce the approved self-service
permission when this service is connected to an API.
"""

from .access_compensation_scope import (
    own_contractor_payment_scope,
    own_employee_payroll_scope,
)
from .models import ContractorPaymentRecord, EmployeePayrollRecord


VISIBLE_STATUSES = (
    "APPROVED",
    "PAID",
)


def _status_label(status):
    if status == "PAID":
        return "Paid"
    if status == "APPROVED":
        return "Approved - Not Yet Paid"
    raise ValueError("Unapproved compensation cannot be disclosed.")


def _money(value):
    return format(value, ".2f")


def own_employee_payroll_disclosure(actor):
    """Disclose only approved or paid payroll for the linked employee."""
    records = own_employee_payroll_scope(actor).filter(
        status__in=VISIBLE_STATUSES,
    )

    return [
        {
            "record_type": "employee_payroll",
            "record_id": str(record.pk),
            "period_start": record.payroll_period_start.isoformat(),
            "period_end": record.payroll_period_end.isoformat(),
            "kind": record.kind,
            "status": record.status,
            "status_label": _status_label(record.status),
            "gross_amount": _money(record.gross_amount),
            "deduction_amount": _money(record.deduction_amount),
            "net_amount": _money(record.net_amount),
        }
        for record in records
    ]


def own_contractor_payment_disclosure(actor):
    """Disclose only approved or paid payments for the linked contractor."""
    records = own_contractor_payment_scope(actor).filter(
        status__in=VISIBLE_STATUSES,
    )

    return [
        {
            "record_type": "contractor_payment",
            "record_id": str(record.pk),
            "period_start": record.payment_period_start.isoformat(),
            "period_end": record.payment_period_end.isoformat(),
            "kind": record.kind,
            "status": record.status,
            "status_label": _status_label(record.status),
            "basis_amount": _money(record.basis_amount),
            "deduction_amount": _money(record.deduction_amount),
            "final_amount": _money(record.final_amount),
        }
        for record in records
    ]
