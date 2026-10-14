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

    return timezone.datetime.fromisoformat(
        evidence.data['deadline']
    ).astimezone(EASTERN)


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

    invoice_signed = verified_signature_time(
        msr,
        CustomerSignatureEvidence.DocumentKind.INVOICE,
    )

    deadline = cancellation_deadline(msr)

    eligible_at = max(
        max(contract_signed, invoice_signed) + timedelta(days=5),
        deadline,
    )

    if timezone.now().astimezone(EASTERN) < eligible_at:
        raise ValidationError(
            'Installation waiting period has not expired.'
        )

    if msr.snapshot.get('financing_type') == 'FINANCED':
        require_financed_deposit(project, msr)

    elif msr.snapshot.get('financing_type') != 'NON_FINANCED':
        raise ValidationError(
            'Approved MSR requires a valid financing classification.'
        )

    return True
