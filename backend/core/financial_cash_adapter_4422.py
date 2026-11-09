"""VERIDIAN 4422: read-only corporate cash evidence preview.

Not connected to operational corporate financial reports.
Does not prove bank reconciliation or statement completeness.
"""

from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from .models import (
    ContractorPaymentRecord,
    ContractorPaymentSettlementVerification,
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerPaymentBankConfirmation,
)


ZERO = Decimal("0.00")


def receipt_evidence_4422(confirmation, has_approved_adjustment):
    payment = confirmation.payment

    if payment.status != CustomerPayment.Status.VERIFIED:
        return None, "Customer payment is not verified"

    if (
        payment.amount <= ZERO
        or payment.verified_at is None
        or payment.verified_by_id is None
    ):
        return None, "Customer payment verification is incomplete"

    if has_approved_adjustment:
        return None, "Approved adjustment requires separate cash review"

    if (
        not confirmation.bank_reference.strip()
        or confirmation.confirmed_by_id is None
        or confirmation.confirmed_at is None
    ):
        return None, "Bank confirmation evidence is incomplete"

    if (
        confirmation.confirmation_date < payment.received_date
        or confirmation.confirmed_at < payment.verified_at
    ):
        return None, "Customer payment evidence dates are inconsistent"

    return payment.amount, None


def settlement_evidence_4422(verification):
    payment = verification.payment_record
    issuance = verification.issuance

    if payment.status != ContractorPaymentRecord.Status.PAID:
        return None, "Contractor payment is not recorded as paid"

    if issuance.payment_record_id != payment.pk:
        return None, "Payment and issuance do not match"

    if (
        verification.payment_record_id != payment.pk
        or verification.cleared_amount <= ZERO
        or verification.cleared_amount != issuance.amount
        or verification.cleared_amount != payment.final_amount
    ):
        return None, "Contractor cleared amount or linkage is invalid"

    if (
        issuance.issued_by_id is None
        or verification.verified_by_id is None
        or issuance.issued_by_id == verification.verified_by_id
        or not verification.evidence_reference.strip()
    ):
        return None, "Independent settlement evidence is incomplete"

    if (
        verification.verified_at < issuance.issued_at
        or verification.settlement_date
        < timezone.localtime(issuance.issued_at).date()
    ):
        return None, "Contractor settlement dates are inconsistent"

    return verification.cleared_amount, None


def preview_cash_evidence_4422(period_start, period_end):
    """Query confirmation and settlement records without writing data."""
    if (
        type(period_start) is not date
        or type(period_end) is not date
        or period_start > period_end
    ):
        raise ValueError("Valid accounting period dates are required.")

    receipts = ZERO
    disbursements = ZERO
    counted = 0
    withheld = []

    confirmations = (
        CustomerPaymentBankConfirmation.objects
        .filter(confirmation_date__range=(period_start, period_end))
        .select_related("payment")
        .order_by("pk")
    )

    for item in confirmations:
        adjusted = CustomerPaymentAdjustment.objects.filter(
            payment_id=item.payment_id,
            status=CustomerPaymentAdjustment.Status.APPROVED,
        ).exists()

        amount, reason = receipt_evidence_4422(item, adjusted)

        if reason is not None:
            withheld.append({
                "kind": "CUSTOMER_RECEIPT",
                "record_id": str(item.pk),
                "reason": reason,
            })
        else:
            receipts += amount
            counted += 1

    settlements = (
        ContractorPaymentSettlementVerification.objects
        .filter(settlement_date__range=(period_start, period_end))
        .select_related("payment_record", "issuance")
        .order_by("pk")
    )

    for item in settlements:
        amount, reason = settlement_evidence_4422(item)

        if reason is not None:
            withheld.append({
                "kind": "CONTRACTOR_SETTLEMENT",
                "record_id": str(item.pk),
                "reason": reason,
            })
        else:
            disbursements += amount
            counted += 1

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "supported_receipts": str(receipts),
        "supported_contractor_disbursements": str(disbursements),
        "partial_net_cash_movement": str(receipts - disbursements),
        "counted_evidence_records": counted,
        "withheld_evidence": withheld,
        "scope_complete": False,
        "bank_reconciled": False,
        "financial_statement_certified": False,
        "operational_approval_performed": False,
    }
