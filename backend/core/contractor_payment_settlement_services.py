"""Independent verification of contractor payment bank settlement."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .contractor_payment_services import _require_contractor_payment_role
from .models import (
    ContractorPaymentIssuance,
    ContractorPaymentRecord,
    ContractorPaymentSettlementVerification,
    Role,
)
from .services import audit


@transaction.atomic
def verify_contractor_payment_settlement(
    actor,
    record_id,
    settlement_date,
    cleared_amount,
    evidence_reference,
):
    """Record independent bank settlement evidence without marking paid."""

    actor = _require_contractor_payment_role(actor, Role.COMPTROLLER)

    record = (
        ContractorPaymentRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != ContractorPaymentRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved contractor payments may have settlement verified.'
        )

    issuance = (
        ContractorPaymentIssuance.objects
        .filter(payment_record=record)
        .first()
    )

    if issuance is None:
        raise ValidationError(
            'CEO payment issuance evidence is required before settlement verification.'
        )

    if issuance.amount != record.final_amount:
        raise ValidationError(
            'The issued payment amount does not match the approved amount.'
        )

    if issuance.issued_by_id == actor.pk:
        raise ValidationError(
            'The payment issuer cannot independently verify settlement.'
        )

    if ContractorPaymentSettlementVerification.objects.filter(
        payment_record=record,
    ).exists():
        raise ValidationError(
            'Settlement verification has already been recorded.'
        )

    if isinstance(settlement_date, datetime):
        raise ValidationError('A settlement date, not a timestamp, is required.')

    if isinstance(settlement_date, str):
        try:
            settlement_date = date.fromisoformat(settlement_date)
        except ValueError:
            raise ValidationError(
                'Settlement date must use YYYY-MM-DD format.'
            )

    if not isinstance(settlement_date, date):
        raise ValidationError(
            'A valid bank settlement date is required.'
        )

    if settlement_date > timezone.localdate():
        raise ValidationError(
            'Bank settlement cannot be verified for a future date.'
        )

    issued_local_date = timezone.localtime(issuance.issued_at).date()

    if settlement_date < issued_local_date:
        raise ValidationError(
            'Bank settlement date cannot precede payment issuance.'
        )

    try:
        cleared_amount = Decimal(str(cleared_amount))
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        raise ValidationError(
            'A valid cleared amount is required.'
        )

    if (
        not cleared_amount.is_finite()
        or cleared_amount != issuance.amount
        or cleared_amount != record.final_amount
    ):
        raise ValidationError(
            'Cleared amount must match the approved and issued payment.'
        )

    if (
        not isinstance(evidence_reference, str)
        or not evidence_reference.strip()
    ):
        raise ValidationError(
            'A bank settlement evidence reference is required.'
        )

    evidence_reference = evidence_reference.strip()

    verified_at = timezone.now()

    if verified_at < issuance.issued_at:
        raise ValidationError(
            'Settlement cannot be verified before payment issuance.'
        )

    verification = ContractorPaymentSettlementVerification.objects.create(
        payment_record=record,
        issuance=issuance,
        verified_by=actor,
        verified_at=verified_at,
        settlement_date=settlement_date,
        cleared_amount=cleared_amount,
        evidence_reference=evidence_reference,
    )

    audit(
        actor,
        'contractor.payment.settlement_verified',
        verification.id,
        {
            'payment_record_id': str(record.id),
            'issuance_id': str(issuance.id),
            'settlement_date': settlement_date.isoformat(),
            'cleared_amount': str(cleared_amount),
            'evidence_reference': evidence_reference,
        },
    )

    return verification