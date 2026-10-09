"""GECC contractor payment creation and approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    ContractorPaymentRecord,
    ContractorCompensationPlan,
)
from .services import (
    audit,
    authorize,
)


@transaction.atomic
def create_contractor_payment_record(
    actor,
    engagement,
    compensation_plan,
    kind,
    payment_period_start,
    payment_period_end,
    basis_amount,
    deduction_amount,
    final_amount,
    calculation_snapshot,
    project=None,
):
    """
    Create a draft contractor payment record.
    """

    if compensation_plan.status != (
        ContractorCompensationPlan.Status.APPROVED
    ):
        raise ValidationError(
            'An approved compensation plan is required.'
        )

    if final_amount < Decimal('0.00'):
        raise ValidationError(
            'Contractor payment cannot be negative.'
        )

    record = ContractorPaymentRecord.objects.create(
        engagement=engagement,
        compensation_plan=compensation_plan,
        project=project,
        kind=kind,
        payment_period_start=payment_period_start,
        payment_period_end=payment_period_end,
        basis_amount=basis_amount,
        deduction_amount=deduction_amount,
        final_amount=final_amount,
        calculation_snapshot=calculation_snapshot,
        created_by=actor,
    )

    audit(
        actor,
        'contractor.payment.created',
        record.id,
        {
            'engagement_id': str(
                engagement.id
            ),
            'kind': kind,
            'amount': str(
                final_amount
            ),
        },
    )

    return record


@transaction.atomic
def approve_contractor_payment_record(
    actor,
    record_id,
):
    """
    Approve a draft contractor payment.
    """

    record = (
        ContractorPaymentRecord.objects
        .select_for_update()
        .select_related('engagement__contractor')
        .get(pk=record_id)
    )

    if record.status != ContractorPaymentRecord.Status.DRAFT:
        raise ValidationError(
            'Only draft contractor payments may be approved.'
        )

    record.status = (
        ContractorPaymentRecord.Status.APPROVED
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
        'contractor.payment.approved',
        record.id,
        {
            'amount': str(
                record.final_amount
            ),
        },
    )

    return record


@transaction.atomic
def mark_contractor_payment_paid(
    actor,
    record_id,
):
    """
    Mark an approved contractor payment as paid.
    """

    record = (
        ContractorPaymentRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != ContractorPaymentRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved contractor payments may be paid.'
        )

    record.status = ContractorPaymentRecord.Status.PAID
    record.paid_at = timezone.now()

    record.save(
        update_fields=[
            'status',
            'paid_at',
        ]
    )

    audit(
        actor,
        'contractor.payment.paid',
        record.id,
        {
            'amount': str(
                record.final_amount
            ),
        },
    )

    return record