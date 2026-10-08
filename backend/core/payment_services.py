"""GECC customer payment verification services."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .contractor_services import require_comptroller
from .models import CustomerPayment, CustomerPaymentAdjustment, Project, MSR
from .services import audit


@transaction.atomic
def verify_customer_payment(actor, payment_id):
    """Verify a customer receipt against its project's approved MSR."""

    require_comptroller(actor)

    payment_ref = CustomerPayment.objects.get(pk=payment_id)

    # Lock the project first, consistent with GECC's MSR workflow.
    project = Project.objects.select_for_update().get(
        pk=payment_ref.project_id
    )

    payment = CustomerPayment.objects.select_for_update().get(
        pk=payment_id
    )

    if payment.status != CustomerPayment.Status.PENDING:
        raise ValidationError(
            'Only pending customer payments may be verified.'
        )

    if project.state == 'CANCELLED':
        raise ValidationError(
            'Payments cannot be verified for cancelled projects.'
        )

    if project.current_approved_id != payment.msr_id:
        raise ValidationError(
            'Payment must reference the current approved MSR.'
        )

    msr = MSR.objects.get(pk=payment.msr_id)

    if msr.project_id != project.id or msr.status != 'APPROVED':
        raise ValidationError(
            'Payment must belong to an approved MSR for this project.'
        )

    if not payment.payment_reference.strip():
        raise ValidationError(
            'A payment reference is required.'
        )

    if payment.amount <= Decimal('0.00'):
        raise ValidationError(
            'Payment amount must be greater than zero.'
        )

    if CustomerPayment.objects.filter(
        project=project,
        payment_reference=payment.payment_reference,
        status=CustomerPayment.Status.VERIFIED,
    ).exclude(pk=payment.pk).exists():
        raise ValidationError(
            'This payment reference has already been verified.'
        )

    try:
        approved_total = Decimal(str(msr.snapshot['total_price']))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise ValidationError(
            'The approved MSR must contain a valid total price.'
        )

    if not approved_total.is_finite() or approved_total <= 0:
        raise ValidationError(
            'The approved MSR total price must be positive.'
        )

    payment.status = CustomerPayment.Status.VERIFIED
    payment.verified_by = actor
    payment.verified_at = timezone.now()

    payment.save(
        update_fields=['status', 'verified_by', 'verified_at']
    )

    audit(
        actor,
        'customer.payment.verified',
        payment.id,
        {
            'project_id': str(project.id),
            'msr_id': str(msr.id),
            'payment_reference': payment.payment_reference,
            'amount': str(payment.amount),
            'approved_total': str(approved_total),
        },
    )

    return payment
def get_project_payment_status(project_id):
    """Calculate payment status against the current approved MSR."""

    project = Project.objects.select_related(
        'current_approved'
    ).get(pk=project_id)

    msr = project.current_approved

    if msr is None or msr.status != 'APPROVED':
        raise ValidationError(
            'Project must have an approved MSR.'
        )

    try:
        approved_total = Decimal(str(msr.snapshot['total_price']))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise ValidationError(
            'Approved MSR must contain a valid total price.'
        )

    if not approved_total.is_finite() or approved_total <= 0:
        raise ValidationError(
            'Approved project total must be positive.'
        )

    verified_payments = CustomerPayment.objects.filter(
        project=project,
        status=CustomerPayment.Status.VERIFIED,
    )

    verified_total = sum(
        (payment.amount for payment in verified_payments),
        Decimal('0.00'),
    )

    approved_adjustments = CustomerPaymentAdjustment.objects.filter(
        payment__project=project,
        payment__status=CustomerPayment.Status.VERIFIED,
        status=CustomerPaymentAdjustment.Status.APPROVED,
    )

    adjustment_total = sum(
        (adjustment.amount for adjustment in approved_adjustments),
        Decimal('0.00'),
    )

    net_received = verified_total - adjustment_total

    outstanding_balance = max(
        approved_total - net_received,
        Decimal('0.00'),
    )

    paid_in_full = net_received >= approved_total
    return {
        'project_id': str(project.id),
        'msr_id': str(msr.id),
        'approved_total': approved_total,
        'verified_total': verified_total,
        'adjustment_total': adjustment_total,
        'net_received': net_received,
        'outstanding_balance': outstanding_balance,
        'paid_in_full': paid_in_full,
    }

@transaction.atomic
def approve_customer_payment_adjustment(actor, adjustment_id):
    """Approve a refund or reversal against a verified receipt."""

    require_comptroller(actor)

    adjustment_ref = CustomerPaymentAdjustment.objects.get(
        pk=adjustment_id
    )

    # Lock the project first to serialize financial decisions.
    project = Project.objects.select_for_update().get(
        pk=adjustment_ref.payment.project_id
    )

    payment = CustomerPayment.objects.select_for_update().get(
        pk=adjustment_ref.payment_id
    )

    adjustment = CustomerPaymentAdjustment.objects.select_for_update().get(
        pk=adjustment_id
    )

    if adjustment.status != CustomerPaymentAdjustment.Status.PENDING:
        raise ValidationError(
            'Only pending adjustments may be approved.'
        )

    if payment.project_id != project.id:
        raise ValidationError(
            'Adjustment payment does not match the project.'
        )

    if payment.status != CustomerPayment.Status.VERIFIED:
        raise ValidationError(
            'Only verified payments may be adjusted.'
        )

    if adjustment.amount <= Decimal('0.00'):
        raise ValidationError(
            'Adjustment amount must be greater than zero.'
        )

    if not adjustment.adjustment_reference.strip():
        raise ValidationError(
            'An adjustment reference is required.'
        )

    if not adjustment.reason.strip():
        raise ValidationError(
            'An adjustment reason is required.'
        )

    approved_adjustments = CustomerPaymentAdjustment.objects.filter(
        payment=payment,
        status=CustomerPaymentAdjustment.Status.APPROVED,
    )

    already_adjusted = sum(
        (item.amount for item in approved_adjustments),
        Decimal('0.00'),
    )

    if already_adjusted + adjustment.amount > payment.amount:
        raise ValidationError(
            'Approved adjustments cannot exceed the original payment.'
        )

    adjustment.status = CustomerPaymentAdjustment.Status.APPROVED
    adjustment.approved_by = actor
    adjustment.approved_at = timezone.now()

    adjustment.save(
        update_fields=['status', 'approved_by', 'approved_at']
    )

    audit(
        actor,
        'customer.payment.adjustment.approved',
        adjustment.id,
        {
            'project_id': str(project.id),
            'payment_id': str(payment.id),
            'adjustment_kind': adjustment.kind,
            'adjustment_amount': str(adjustment.amount),
            'adjustment_reference': adjustment.adjustment_reference,
        },
    )

    return adjustment
