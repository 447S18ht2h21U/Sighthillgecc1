"""Shared, read-only installation payment readiness calculation."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework.exceptions import ValidationError

from .ceo_payment_exception_services import has_valid_payment_exception
from .models import (
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerPaymentBankConfirmation,
    MSR,
)


MONEY = Decimal("0.01")
HALF = Decimal("0.50")


def installation_payment_readiness(project):
    """Calculate qualifying bank-available funds for the current approved MSR."""

    msr = project.current_approved

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        raise ValidationError(
            "Installation requires a current approved Master Sales Record."
        )

    financing = msr.snapshot.get("financing_type")

    if financing not in ("FINANCED", "NON_FINANCED"):
        raise ValidationError(
            "The approved Master Sales Record needs a valid financing classification."
        )

    payment_option = msr.snapshot.get("payment_option")

    if payment_option not in (
        "50_PERCENT_DEPOSIT",
        "100_PERCENT_COMPLETION",
    ):
        raise ValidationError(
            "The approved Master Sales Record needs a valid payment option."
        )

    try:
        approved_total = Decimal(str(msr.snapshot["total_price"]))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise ValidationError(
            "The approved Master Sales Record needs a valid total price."
        )

    if not approved_total.is_finite() or approved_total <= Decimal("0.00"):
        raise ValidationError(
            "The approved project total must be greater than zero."
        )

    required_deposit = (
        approved_total * HALF
    ).quantize(MONEY, rounding=ROUND_HALF_UP)

    payments = CustomerPayment.objects.filter(
        project=project,
        msr=msr,
        status=CustomerPayment.Status.VERIFIED,
        bank_confirmation__isnull=False,
    )

    bank_confirmed_total = sum(
        (payment.amount for payment in payments),
        Decimal("0.00"),
    )

    adjustments = CustomerPaymentAdjustment.objects.filter(
        payment__in=payments,
        status=CustomerPaymentAdjustment.Status.APPROVED,
    )

    adjustment_total = sum(
        (adjustment.amount for adjustment in adjustments),
        Decimal("0.00"),
    )

    qualifying_funds = max(
        bank_confirmed_total - adjustment_total,
        Decimal("0.00"),
    )

    remaining_deposit = max(
        required_deposit - qualifying_funds,
        Decimal("0.00"),
    )

    exception_valid = has_valid_payment_exception(project, msr)

    if exception_valid:
        payment_ready = True
        explanation = (
            "A valid CEO payment exception permits payment after completion. "
            "Other installation requirements still apply."
        )
    elif qualifying_funds >= required_deposit:
        payment_ready = True
        explanation = (
            "The required deposit is confirmed available at the bank."
        )
    else:
        payment_ready = False
        explanation = (
            f"Deposit required: ${required_deposit:,.2f}. "
            f"Bank-confirmed funds remaining: ${qualifying_funds:,.2f}. "
            f"Additional funds needed: ${remaining_deposit:,.2f}."
        )

    return {
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "financing_type": financing,
        "payment_option": payment_option,
        "approved_total": approved_total,
        "required_deposit": required_deposit,
        "bank_confirmed_total": bank_confirmed_total,
        "approved_adjustments": adjustment_total,
        "qualifying_funds": qualifying_funds,
        "remaining_deposit": remaining_deposit,
        "ceo_exception_valid": exception_valid,
        "payment_ready": payment_ready,
        "explanation": explanation,
    }
