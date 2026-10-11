"""GECC employee payroll creation and approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    EmployeePayrollRecord,
    EmployeeCompensationPlan,
    EmployeePayrollPaymentIssuance,
    Role,
    User,
)
from .services import (
    audit,
)


def _require_payroll_role(actor, required_role):
    current_actor = User.objects.filter(pk=actor.pk, is_active=True).first() if actor is not None and getattr(actor, 'pk', None) is not None else None
    if current_actor is None or current_actor.role != required_role:
        raise PermissionDenied('An active user with the required payroll role is required.')
    return current_actor


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

    actor = _require_payroll_role(actor, Role.COMPTROLLER)

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

    actor = _require_payroll_role(actor, Role.CEO)

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

    actor = _require_payroll_role(actor, Role.COMPTROLLER)

    record = (
        EmployeePayrollRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != EmployeePayrollRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved payroll records may be paid.'
        )

    issuance = EmployeePayrollPaymentIssuance.objects.filter(
        payroll_record=record,
        amount=record.net_amount,
    ).first()
    if issuance is None:
        raise ValidationError(
            'Matching CEO payment issuance evidence is required before payroll can be marked paid.'
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


@transaction.atomic
def issue_employee_payroll_payment(
    actor,
    record_id,
    amount,
    payment_method,
    transaction_reference,
    supporting_evidence='',
):
    """Record CEO-issued payment without marking payroll paid."""
    actor = _require_payroll_role(actor, Role.CEO)

    record = (
        EmployeePayrollRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != EmployeePayrollRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved employee payroll may be issued for payment.'
        )

    try:
        amount = Decimal(str(amount))
    except (TypeError, ValueError, ArithmeticError):
        raise ValidationError('A valid payment amount is required.')

    if not amount.is_finite() or amount != record.net_amount:
        raise ValidationError(
            'Payment issuance amount must equal approved net payroll.'
        )

    if payment_method not in EmployeePayrollPaymentIssuance.Method.values:
        raise ValidationError('A valid payment method is required.')

    if (
        not isinstance(transaction_reference, str)
        or not transaction_reference.strip()
        or len(transaction_reference) > 200
    ):
        raise ValidationError(
            'A transaction reference of 1 to 200 characters is required.'
        )

    if supporting_evidence is None:
        supporting_evidence = ''
    if not isinstance(supporting_evidence, str):
        raise ValidationError('Supporting evidence must be text.')

    if EmployeePayrollPaymentIssuance.objects.filter(
        payroll_record=record,
    ).exists():
        raise ValidationError(
            'Payment issuance has already been recorded for this payroll.'
        )

    issuance = EmployeePayrollPaymentIssuance.objects.create(
        payroll_record=record,
        issued_by=actor,
        issued_at=timezone.now(),
        amount=amount,
        payment_method=payment_method,
        transaction_reference=transaction_reference.strip(),
        supporting_evidence=supporting_evidence,
    )

    audit(
        actor,
        'employee.payroll.payment_issued',
        issuance.id,
        {
            'payroll_record_id': str(record.id),
            'amount': str(amount),
            'payment_method': payment_method,
            'transaction_reference': transaction_reference.strip(),
        },
    )

    return issuance