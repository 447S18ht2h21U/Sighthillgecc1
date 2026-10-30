"""Read-only, person-specific compensation-period report foundation.

This service is not connected to a live API. A future API must
independently enforce its approved self-service permission.

No administrative or company-wide compensation access is granted.
"""

from .access_compensation_scope import (
    own_contractor_payment_scope,
    own_employee_payroll_scope,
)
from .individual_compensation_report_dates import (
    validate_individual_report_dates,
)
from .individual_compensation_report_periods import (
    compensation_period_filter_bounds,
)
from .models import ContractorPaymentRecord, EmployeePayrollRecord


VISIBLE_STATUSES = ("APPROVED", "PAID")


def _status_label(status):
    if status == "PAID":
        return "Paid"
    if status == "APPROVED":
        return "Approved - Not Yet Paid"
    raise ValueError("Unapproved compensation cannot be reported.")


def _money(value):
    return format(value, ".2f")


def own_individual_compensation_period_report(
    actor,
    start_date,
    end_date,
):
    """Return only approved/paid compensation owned by the actor.

    Period selection uses inclusive overlap. Amounts represent the
    full underlying obligation, not a prorated portion of the selected
    report period. No financial records are changed.
    """

    start, end = validate_individual_report_dates(
        start_date,
        end_date,
    )

    bounds = compensation_period_filter_bounds(start, end)

    employees = (
        own_employee_payroll_scope(actor)
        .filter(
            status__in=VISIBLE_STATUSES,
            payroll_period_start__lte=bounds[
                "period_start_on_or_before"
            ],
            payroll_period_end__gte=bounds[
                "period_end_on_or_after"
            ],
        )
        .order_by("payroll_period_start", "pk")
    )

    contractors = (
        own_contractor_payment_scope(actor)
        .filter(
            status__in=VISIBLE_STATUSES,
            payment_period_start__lte=bounds[
                "period_start_on_or_before"
            ],
            payment_period_end__gte=bounds[
                "period_end_on_or_after"
            ],
        )
        .order_by("payment_period_start", "pk")
    )

    employee_rows = [
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
        for record in employees
    ]

    contractor_rows = [
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
        for record in contractors
    ]

    return {
        "report_type": "individual_compensation_period",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_basis": "inclusive_overlap",
        "amount_basis": "full_obligation_not_prorated",
        "employee_records": employee_rows,
        "contractor_records": contractor_rows,
    }