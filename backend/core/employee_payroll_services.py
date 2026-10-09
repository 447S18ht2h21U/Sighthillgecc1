"""GECC employee payroll creation and approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    EmployeePayrollRecord,
    EmployeeCompensationPlan,
)
from .services import (
    audit,
)


@transaction.atomic
def create_employee_payroll_record(
    actor,
    employee,
    compensation_plan,
    kind,
    payroll_period_start,
    payroll_period_end,
    gross_amount,
    deduction_amount,
    net_amount,
    calculation_snapshot,
):
    """
    Create a draft employee payroll record.
    """

    if compensation_plan.status != (
        EmployeeCompensationPlan.Status.APPROVED
    ):
        raise ValidationError(
            'An approved employee compensation plan is required.'
        )

    if gross_amount < Decimal('0.00'):
        raise ValidationError(
            'Employee payroll cannot be negative.'
        )

    if net_amount < Decimal('0.00'):
        raise ValidationError(
            'Employee net pay cannot be negative.'
        )

    record = EmployeePayrollRecord.objects.create(
        employee=employee,
        compensation_plan=compensation_plan,
        kind=kind,
        payroll_period_start=payroll_period_start,
        payroll_period_end=payroll_period_end,
        gross_amount=gross_amount,
        deduction_amount=deduction_amount,
        net_amount=net_amount,
        calculation_snapshot=calculation_snapshot,
        created_by=actor,
    )

    audit(
        actor,
        'employee.payroll.created',
        record.id,
        {
            'employee_id': str(
                employee.id
            ),
            'amount': str(
                net_amount
            ),
        },
    )

    return record


@transaction.atomic
def approve_employee_payroll_record(
    actor,
    record_id,
):
    """
    Approve a draft employee payroll record.
    """

    record = (
        EmployeePayrollRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != EmployeePayrollRecord.Status.DRAFT:
        raise ValidationError(
            'Only draft payroll records may be approved.'
        )

    record.status = (
        EmployeePayrollRecord.Status.APPROVED
    )

    record.approved_by = actor
    record.approved_at = timezone.now()

    record.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_at',
        ]
    )

    audit(
        actor,
        'employee.payroll.approved',
        record.id,
        {
            'amount': str(
                record.net_amount
            ),
        },
    )

    return record


@transaction.atomic
def mark_employee_payroll_paid(
    actor,
    record_id,
):
    """
    Mark an approved employee payroll record as paid.
    """

    record = (
        EmployeePayrollRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != EmployeePayrollRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved payroll records may be paid.'
        )

    record.status = EmployeePayrollRecord.Status.PAID
    record.paid_at = timezone.now()

    record.save(
        update_fields=[
            'status',
            'paid_at',
        ]
    )

    audit(
        actor,
        'employee.payroll.paid',
        record.id,
        {
            'amount': str(
                record.net_amount
            ),
        },
    )

    return record