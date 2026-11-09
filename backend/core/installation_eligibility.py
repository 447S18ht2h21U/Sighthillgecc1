from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerSignatureEvidence,
    ProjectEvidence,
)
from .rules import EASTERN


def parse_verified_cancellation_deadline(value):
    from django.utils.dateparse import parse_datetime

    try:
        parsed = parse_datetime(value) if isinstance(value, str) else None
    except (TypeError, ValueError, OverflowError):
        parsed = None

    if parsed is None or timezone.is_naive(parsed):
        raise ValidationError("Valid cancellation deadline with UTC offset is required.")

    return parsed.astimezone(EASTERN)


def require_current_approved_msr(project):
    msr = project.current_approved
    if msr is None or msr.status != 'APPROVED':
        raise ValidationError('Installation requires a current approved MSR.')
    return msr


def verified_signature_time(msr, document_kind):
    evidence = CustomerSignatureEvidence.objects.filter(
        msr=msr,
        document_kind=document_kind,
    ).order_by('-created_at', '-id').first()

    if evidence is None:
        raise ValidationError(
            f'Verified {document_kind.lower()} signature evidence is required.'
        )

    return evidence.signed_at.astimezone(EASTERN)


def cancellation_deadline(msr):
    evidence = ProjectEvidence.objects.filter(
        msr=msr,
        kind='CANCELLATION_DEADLINE',
    ).order_by('-created_at', '-id').first()

    if (
        evidence is None
        or evidence.data.get('verified') is not True
        or 'deadline' not in evidence.data
    ):
        raise ValidationError(
            'Verified cancellation deadline evidence is required.'
        )

    return parse_verified_cancellation_deadline(evidence.data['deadline'])


def require_financed_deposit(project, msr):
    try:
        total = Decimal(str(msr.snapshot['total_price']))
    except (KeyError, TypeError, InvalidOperation):
        raise ValidationError('Approved MSR total price is invalid.')

    required = total * Decimal('0.50')

    payments = CustomerPayment.objects.filter(
        project=project,
        msr=msr,
        status=CustomerPayment.Status.VERIFIED,
    )

    received = sum(
        (payment.amount for payment in payments),
        Decimal('0.00'),
    )

    adjustments = CustomerPaymentAdjustment.objects.filter(
        payment__in=payments,
        status=CustomerPaymentAdjustment.Status.APPROVED,
    )

    adjusted = sum(
        (item.amount for item in adjustments),
        Decimal('0.00'),
    )

    if received - adjusted < required:
        raise ValidationError(
            'Verified 50% deposit is required before installation.'
        )


def ensure_installation_eligible(project):
    msr = require_current_approved_msr(project)

    contract_signed = verified_signature_time(
        msr,
        CustomerSignatureEvidence.DocumentKind.CONTRACT,
    )

    deadline = cancellation_deadline(msr)

    eligible_at = max(
        contract_signed + timedelta(days=5),
        deadline,
    )

    if timezone.now().astimezone(EASTERN) < eligible_at:
        raise ValidationError(
            'Installation waiting period has not expired.'
        )

    from .installation_payment_readiness import installation_payment_readiness

    payment = installation_payment_readiness(project)

    if not payment["payment_ready"]:
        raise ValidationError(payment["explanation"])

    return True
