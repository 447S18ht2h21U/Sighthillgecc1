"""Read-only supplement for missing employee payroll cash evidence.

Operational dates are for identifying records, not bank settlement.
This module is not registered as a live API or financial report.
"""

from datetime import date

from django.utils import timezone

from .models import (
    EmployeePayrollPaymentIssuance,
    EmployeePayrollRecord,
)


def issuance_gap_4430(issuance):
    record = issuance.payroll_record
    if record.status != EmployeePayrollRecord.Status.APPROVED:
        return None

    if issuance.amount != record.net_amount:
        reason = "Issued amount does not match approved net payroll."
    else:
        reason = (
            "CEO payment issuance is recorded, but payroll is not "
            "marked Paid and independent bank settlement is unverified."
        )

    return {
        "kind": "EMPLOYEE_ISSUED_NOT_PAID",
        "record_id": str(record.pk),
        "issuance_id": str(issuance.pk),
        "amount": str(issuance.amount),
        "review_date": timezone.localtime(issuance.issued_at).date().isoformat(),
        "review_date_type": "ISSUANCE_DATE_NOT_SETTLEMENT",
        "cash_settlement_verified": False,
        "reason": reason,
    }


def missing_paid_date_gap_4430(record):
    if (
        record.status != EmployeePayrollRecord.Status.PAID
        or record.paid_at is not None
    ):
        return None

    return {
        "kind": "EMPLOYEE_PAID_WITHOUT_TIMESTAMP",
        "record_id": str(record.pk),
        "amount": str(record.net_amount),
        "review_date": None,
        "review_date_type": "MISSING_PAID_TIMESTAMP",
        "cash_settlement_verified": False,
        "reason": (
            "Payroll is marked Paid without a Paid timestamp. "
            "Independent bank settlement is also unverified."
        ),
    }


def preview_payroll_cash_gaps_4430(start, end):
    if type(start) is not date or type(end) is not date or start > end:
        raise ValueError("Valid review dates are required.")

    exceptions = []

    issuances = (
        EmployeePayrollPaymentIssuance.objects
        .filter(
            issued_at__date__range=(start, end),
            payroll_record__status=EmployeePayrollRecord.Status.APPROVED,
        )
        .select_related("payroll_record")
        .order_by("pk")
    )

    for issuance in issuances:
        item = issuance_gap_4430(issuance)
        if item is not None:
            exceptions.append(item)

    # No cash date exists for these records. Use payroll period
    # end only to select a REVIEW cohort, not a cash period.
    undated_paid = (
        EmployeePayrollRecord.objects
        .filter(
            status=EmployeePayrollRecord.Status.PAID,
            paid_at__isnull=True,
            payroll_period_end__range=(start, end),
        )
        .order_by("pk")
    )

    for record in undated_paid:
        item = missing_paid_date_gap_4430(record)
        if item is not None:
            exceptions.append(item)

    return {
        "review_start": start.isoformat(),
        "review_end": end.isoformat(),
        "exceptions": exceptions,
        "exception_count": len(exceptions),
        "date_scope": (
            "ISSUANCE_DATE_OR_PAYROLL_PERIOD_END_REVIEW_ONLY"
        ),
        "bank_reconciled": False,
        "cash_flow_complete": False,
        "financial_statement_certified": False,
        "operational_changes_performed": False,
        "limitations": (
            "The issued-not-Paid category omits records with no "
            "issuance. Missing Paid timestamps are grouped by "
            "payroll period end, not by actual cash date. "
            "Paid payroll with timestamps remains in the "
            "separate Step 4428 exception report."
        ),
    }
