"""GECC contractor payment creation and approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    ContractorPaymentRecord,
    ContractorPaymentIssuance,
    ContractorPaymentSettlementVerification,
    ContractorCompensationPlan,
    Role,
    User,
)
from .services import (
    audit,
    authorize,
)


def _require_contractor_payment_role(actor, required_role):
    """Verify the current active user and role against the database."""
    actor_id = getattr(actor, "pk", None)

    current_actor = (
        User.objects.filter(pk=actor_id, is_active=True).first()
        if actor_id is not None else None
    )

    if current_actor is None or current_actor.role != required_role:
        raise PermissionDenied(
            "An active user with the required contractor payment role is required."
        )

    return current_actor


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

    actor = _require_contractor_payment_role(actor, Role.COMPTROLLER)

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

    actor = _require_contractor_payment_role(actor, Role.CEO)

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
def mark_contractor_payment_paid(actor, record_id):
    """Mark paid only after independent, matching bank settlement."""

    actor = _require_contractor_payment_role(actor, Role.COMPTROLLER)

    record = (
        ContractorPaymentRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != ContractorPaymentRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved contractor payments may be marked paid.'
        )

    issuance = ContractorPaymentIssuance.objects.filter(
        payment_record=record,
        amount=record.final_amount,
    ).first()

    if issuance is None:
        raise ValidationError(
            'Matching CEO payment issuance evidence is required.'
        )

    verification = ContractorPaymentSettlementVerification.objects.filter(
        payment_record=record,
        issuance=issuance,
        cleared_amount=record.final_amount,
    ).first()

    if verification is None:
        raise ValidationError(
            'Independent matching bank settlement verification is required.'
        )

    if issuance.issued_by_id == verification.verified_by_id:
        raise ValidationError(
            'Payment issuance and settlement verification must be independent.'
        )

    if verification.verified_at < issuance.issued_at:
        raise ValidationError(
            'Settlement verification cannot precede payment issuance.'
        )

    if not isinstance(verification.evidence_reference, str) or not verification.evidence_reference.strip():
        raise ValidationError(
            'Bank settlement evidence is required.'
        )

    record.status = ContractorPaymentRecord.Status.PAID
    record.paid_at = timezone.now()
    record.save(update_fields=['status', 'paid_at'])

    audit(
        actor,
        'contractor.payment.paid',
        record.id,
        {
            'amount': str(record.final_amount),
            'issuance_id': str(issuance.id),
            'settlement_verification_id': str(verification.id),
            'settlement_date': verification.settlement_date.isoformat(),
            'evidence_reference': verification.evidence_reference,
        },
    )

    return record
