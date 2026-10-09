"""GECC payroll summary creation and approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    ContractorPaymentRecord,
    EmployeePayrollRecord,
    PayrollSummary,
)
from .services import (
    audit,
)


@transaction.atomic
def create_payroll_summary(
    actor,
    period_start,
    period_end,
):
    """
    Create a draft payroll summary from paid payroll records.
    """

    if period_end < period_start:
        raise ValidationError(
            'Payroll period end cannot be before start date.'
        )

    existing = PayrollSummary.objects.filter(
        period_start=period_start,
        period_end=period_end,
    ).first()

    if existing:
        raise ValidationError(
            'A payroll summary already exists for this period.'
        )

    contractor_records = (
        ContractorPaymentRecord.objects
        .filter(
            status=ContractorPaymentRecord.Status.PAID,
            paid_at__date__gte=period_start,
            paid_at__date__lte=period_end,
        )
    )

    employee_records = (
        EmployeePayrollRecord.objects
        .filter(
            status=EmployeePayrollRecord.Status.PAID,
            paid_at__date__gte=period_start,
            paid_at__date__lte=period_end,
        )
    )

    contractor_total = sum(
        (
            record.final_amount
            for record in contractor_records
        ),
        Decimal('0.00'),
    )

    employee_total = sum(
        (
            record.net_amount
            for record in employee_records
        ),
        Decimal('0.00'),
    )

    snapshot = {
        'contractor_records': [
            {
                'id': str(record.id),
                'amount': str(record.final_amount),
                'kind': record.kind,
            }
            for record in contractor_records
        ],
        'employee_records': [
            {
                'id': str(record.id),
                'amount': str(record.net_amount),
                'kind': record.kind,
            }
            for record in employee_records
        ],
    }

    summary = PayrollSummary.objects.create(
        period_start=period_start,
        period_end=period_end,
        contractor_total=contractor_total,
        employee_total=employee_total,
        total_payroll_expense=(
            contractor_total + employee_total
        ),
        summary_snapshot=snapshot,
        created_by=actor,
    )

    audit(
        actor,
        'payroll.summary.created',
        summary.id,
        {
            'period_start': str(period_start),
            'period_end': str(period_end),
            'contractor_total': str(contractor_total),
            'employee_total': str(employee_total),
        },
    )

    return summary


@transaction.atomic
def approve_payroll_summary(
    actor,
    summary_id,
):
    """
    Approve a draft payroll summary.
    """

    summary = (
        PayrollSummary.objects
        .select_for_update()
        .get(pk=summary_id)
    )

    if summary.status != PayrollSummary.Status.DRAFT:
        raise ValidationError(
            'Only draft payroll summaries may be approved.'
        )

    summary.status = PayrollSummary.Status.APPROVED
    summary.approved_by = actor
    summary.approved_at = timezone.now()

    summary.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_at',
        ]
    )

    audit(
        actor,
        'payroll.summary.approved',
        summary.id,
        {
            'period_start': str(summary.period_start),
            'period_end': str(summary.period_end),
        },
    )

    return summary