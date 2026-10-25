"""Audited confirmation that a verified customer payment is bank-available."""

from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .contractor_services import require_comptroller
from .models import (
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerPaymentBankConfirmation,
    MSR,
    Project,
)
from .services import audit


EASTERN = ZoneInfo("America/New_York")


def _required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} is required.")
    return value.strip()


@transaction.atomic
def confirm_customer_payment_bank_availability(
    *,
    actor,
    payment_id,
    bank_reference,
    confirmation_date,
    confirmation_method,
    confirmation_note,
):
    """Record one irreversible, audited bank-availability confirmation."""

    require_comptroller(actor)

    bank_reference = _required_text(
        bank_reference, "Bank reference"
    )
    confirmation_method = _required_text(
        confirmation_method, "Confirmation method"
    )
    confirmation_note = _required_text(
        confirmation_note, "Confirmation explanation"
    )

    if not isinstance(confirmation_date, date) or isinstance(
        confirmation_date, __import__("datetime").datetime
    ):
        raise ValidationError(
            "Enter a valid funds-available calendar date."
        )

    payment_ref = CustomerPayment.objects.get(pk=payment_id)

    project = Project.objects.select_for_update().get(
        pk=payment_ref.project_id
    )
    payment = CustomerPayment.objects.select_for_update().get(
        pk=payment_id
    )
    msr = MSR.objects.select_for_update().get(pk=payment.msr_id)

    if payment.project_id != project.pk or msr.project_id != project.pk:
        raise ValidationError(
            "The payment, project, and Master Sales Record must match."
        )

    if msr.status != "APPROVED":
        raise ValidationError(
            "The payment must reference an approved Master Sales Record."
        )

    if payment.status != CustomerPayment.Status.VERIFIED:
        raise ValidationError(
            "Only verified customer payments may be bank-confirmed."
        )

    if (
        payment.amount <= Decimal("0.00")
        or payment.verified_at is None
        or payment.verified_by_id is None
    ):
        raise ValidationError(
            "The payment must have a valid amount and verification."
        )

    if CustomerPaymentBankConfirmation.objects.filter(
        payment=payment
    ).exists():
        raise ValidationError(
            "Bank availability has already been confirmed for this payment."
        )

    approved_adjustments = CustomerPaymentAdjustment.objects.filter(
        payment=payment,
        status=CustomerPaymentAdjustment.Status.APPROVED,
    )

    adjusted_amount = sum(
        (item.amount for item in approved_adjustments),
        Decimal("0.00"),
    )

    if adjusted_amount >= payment.amount:
        raise ValidationError(
            "A fully refunded or reversed payment cannot be bank-confirmed."
        )

    confirmed_at = timezone.now()
    today_eastern = confirmed_at.astimezone(EASTERN).date()

    if confirmation_date < payment.received_date:
        raise ValidationError(
            "Funds cannot be available before the recorded payment date."
        )

    if confirmation_date > today_eastern:
        raise ValidationError(
            "The funds-available date cannot be in the future."
        )

    if confirmed_at < payment.verified_at:
        raise ValidationError(
            "Bank confirmation cannot precede payment verification."
        )

    confirmation = CustomerPaymentBankConfirmation.objects.create(
        payment=payment,
        bank_reference=bank_reference,
        confirmation_date=confirmation_date,
        confirmation_method=confirmation_method,
        confirmation_note=confirmation_note,
        confirmed_by=actor,
        confirmed_at=confirmed_at,
    )

    audit(
        actor,
        "customer.payment.bank_availability.confirmed",
        confirmation.pk,
        {
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "payment_id": str(payment.pk),
            "payment_reference": payment.payment_reference,
            "payment_amount": str(payment.amount),
            "bank_reference": bank_reference,
            "confirmation_date": confirmation_date.isoformat(),
            "confirmation_method": confirmation_method,
            "confirmation_note": confirmation_note,
            "confirmed_at": confirmed_at.isoformat(),
        },
    )

    return confirmation
