"""Read-only cash evidence exceptions; not a financial statement.

The date fields below identify operational records for review.
They are NOT confirmed bank settlement dates.
"""

from datetime import date

from .models import CustomerPaymentAdjustment, EmployeePayrollRecord


def _valid_period(start, end):
    if type(start) is not date or type(end) is not date or start > end:
        raise ValueError("Valid accounting review dates required.")


def refund_exception_4428(adjustment):
    if adjustment.status != CustomerPaymentAdjustment.Status.APPROVED:
        return None
    return {
        "kind": "CUSTOMER_REFUND_OR_REVERSAL",
        "record_id": str(adjustment.pk),
        "amount": str(adjustment.amount),
        "review_date": adjustment.adjustment_date.isoformat(),
        "review_date_type": "ADJUSTMENT_DATE_NOT_SETTLEMENT",
        "cash_settlement_verified": False,
        "reason": (
            "Approval and adjustment date do not prove "
            "bank refund or reversal settlement."
        ),
    }


def payroll_exception_4428(payroll):
    if payroll.status != EmployeePayrollRecord.Status.PAID:
        return None
    if payroll.paid_at is None:
        return {
            "kind": "EMPLOYEE_PAYROLL_SETTLEMENT",
            "record_id": str(payroll.pk),
            "amount": str(payroll.net_amount),
            "review_date": None,
            "review_date_type": "MISSING_PAID_TIMESTAMP",
            "cash_settlement_verified": False,
            "reason": "Paid payroll record lacks a status timestamp.",
        }
    return {
        "kind": "EMPLOYEE_PAYROLL_SETTLEMENT",
        "record_id": str(payroll.pk),
        "amount": str(payroll.net_amount),
        "review_date": payroll.paid_at.date().isoformat(),
        "review_date_type": "PAID_STATUS_DATE_NOT_SETTLEMENT",
        "cash_settlement_verified": False,
        "reason": (
            "Payroll Paid status and CEO issuance do not "
            "independently verify bank settlement."
        ),
    }


def preview_cash_exceptions_4428(start, end):
    """Read records only. This is a scoped evidence gap inventory."""
    _valid_period(start, end)

    exceptions = []

    adjustments = (
        CustomerPaymentAdjustment.objects
        .filter(
            status=CustomerPaymentAdjustment.Status.APPROVED,
            adjustment_date__range=(start, end),
        )
        .order_by("pk")
    )
    for adjustment in adjustments:
        exception = refund_exception_4428(adjustment)
        if exception is not None:
            exceptions.append(exception)

    payroll = (
        EmployeePayrollRecord.objects
        .filter(
            status=EmployeePayrollRecord.Status.PAID,
            paid_at__date__range=(start, end),
        )
        .order_by("pk")
    )
    for record in payroll:
        exception = payroll_exception_4428(record)
        if exception is not None:
            exceptions.append(exception)

    return {
        "review_period_start": start.isoformat(),
        "review_period_end": end.isoformat(),
        "exceptions": exceptions,
        "exception_count": len(exceptions),
        "date_scope": "OPERATIONAL_DATES_ONLY",
        "bank_reconciled": False,
        "cash_flow_complete": False,
        "financial_statement_certified": False,
        "operational_changes_performed": False,
        "limitations": (
            "Not an exhaustive inventory. Missing-date payroll, "
            "unapproved adjustments, employee issuance-only records, "
            "and other bank movements need separate reconciliation."
        ),
    }
