"""Consolidated read-only cash evidence exception inventory.

This is a partial, review-date-scoped evidence inventory, not a
cash-flow statement, bank reconciliation, or financial approval.
"""

from datetime import date

from .financial_cash_exceptions_4428 import preview_cash_exceptions_4428
from .financial_payroll_cash_gaps_4430 import preview_payroll_cash_gaps_4430
from .models import EmployeePayrollRecord


def preview_cash_exception_inventory_4431(start, end):
    if type(start) is not date or type(end) is not date or start > end:
        raise ValueError("Valid review dates required.")

    previous = preview_cash_exceptions_4428(start, end)
    additional = preview_payroll_cash_gaps_4430(start, end)

    items = list(previous["exceptions"]) + list(additional["exceptions"])

    # This category uses payroll period end as a review cohort only.
    # It does not identify a bank payment or settlement date.
    unissued = (
        EmployeePayrollRecord.objects
        .filter(
            status=EmployeePayrollRecord.Status.APPROVED,
            payroll_period_end__range=(start, end),
            payment_issuance__isnull=True,
        )
        .order_by("pk")
    )

    for record in unissued:
        items.append({
            "kind": "EMPLOYEE_APPROVED_NOT_ISSUED",
            "record_id": str(record.pk),
            "amount": str(record.net_amount),
            "review_date": record.payroll_period_end.isoformat(),
            "review_date_type": "PAYROLL_PERIOD_END_NOT_CASH_DATE",
            "cash_settlement_verified": False,
            "reason": (
                "Approved payroll has no recorded CEO issuance. "
                "No cash settlement may be inferred."
            ),
        })

    keys = [(item["kind"], item["record_id"]) for item in items]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate cash evidence exception detected.")

    return {
        "review_start": start.isoformat(),
        "review_end": end.isoformat(),
        "exceptions": items,
        "exception_count": len(items),
        "date_scope": "MIXED_OPERATIONAL_REVIEW_DATES_NOT_CASH_DATES",
        "inventory_complete": False,
        "bank_reconciled": False,
        "financial_statement_certified": False,
        "operational_changes_performed": False,
        "limitations": (
            "Not exhaustive. Independent payroll settlement, refund "
            "clearing, missing historical evidence, and complete bank "
            "transaction reconciliation remain outstanding."
        ),
    }
