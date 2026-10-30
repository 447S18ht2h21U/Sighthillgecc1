"""Audited CEO issuance of approved contractor payments."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .contractor_payment_services import _require_contractor_payment_role
from .models import (
    ContractorPaymentIssuance,
    ContractorPaymentRecord,
    Role,
)
from .services import audit


@transaction.atomic
def issue_contractor_payment(
    actor,
    record_id,
    amount,
    payment_method,
    transaction_reference,
    supporting_evidence='',
):
    """Record CEO-issued payment without marking the obligation paid."""

    actor = _require_contractor_payment_role(actor, Role.CEO)

    record = (
        ContractorPaymentRecord.objects
        .select_for_update()
        .get(pk=record_id)
    )

    if record.status != ContractorPaymentRecord.Status.APPROVED:
        raise ValidationError(
            'Only approved contractor payments may be issued.'
        )

    if record.approved_by_id is None or record.approved_at is None:
        raise ValidationError(
            'Recorded CEO approval is required before payment issuance.'
        )

    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError, ArithmeticError):
        raise ValidationError(
            'A valid payment amount is required.'
        )

    if not amount.is_finite() or amount != record.final_amount:
        raise ValidationError(
            'Payment issuance amount must equal the approved amount.'
        )

    if payment_method not in ContractorPaymentIssuance.Method.values:
        raise ValidationError(
            'A valid payment method is required.'
        )

    if (
        not isinstance(transaction_reference, str)
        or not transaction_reference.strip()
        or len(transaction_reference.strip()) > 200
    ):
        raise ValidationError(
            'A transaction reference of 1 to 200 characters is required.'
        )

    if supporting_evidence is None:
        supporting_evidence = ''

    if not isinstance(supporting_evidence, str):
        raise ValidationError(
            'Supporting payment evidence must be text.'
        )

    if ContractorPaymentIssuance.objects.filter(
        payment_record=record,
    ).exists():
        raise ValidationError(
            'Contractor payment issuance has already been recorded.'
        )

    reference = transaction_reference.strip()

    issuance = ContractorPaymentIssuance.objects.create(
        payment_record=record,
        issued_by=actor,
        issued_at=timezone.now(),
        amount=amount,
        payment_method=payment_method,
        transaction_reference=reference,
        supporting_evidence=supporting_evidence,
    )

    audit(
        actor,
        'contractor.payment.payment_issued',
        issuance.id,
        {
            'payment_record_id': str(record.id),
            'amount': str(amount),
            'payment_method': payment_method,
            'transaction_reference': reference,
        },
    )

    return issuance