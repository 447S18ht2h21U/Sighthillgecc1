"""Test-only, read-only cash readiness and evidence gap preview.

Not registered as an operational API. Does not approve, certify,
or replace corporate accounting statements or bank reconciliation.
"""

from datetime import date

from .financial_cash_adapter_4422 import preview_cash_evidence_4422
from .financial_cash_inventory_4431 import (
    preview_cash_exception_inventory_4431,
)
from .models import (
    ContractorPaymentIssuance,
    ContractorPaymentRecord,
    ContractorPaymentSettlementVerification,
    CustomerPayment,
)


def preview_financial_cash_readiness_4432(start, end):
    if type(start) is not date or type(end) is not date or start > end:
        raise ValueError("Valid review period dates required.")

    cash = preview_cash_evidence_4422(start, end)
    review = preview_cash_exception_inventory_4431(start, end)
    exceptions = list(review["exceptions"])

    # Received date selects a review cohort, not proven bank availability.
    unconfirmed = (
        CustomerPayment.objects
        .filter(
            status=CustomerPayment.Status.VERIFIED,
            received_date__range=(start, end),
            bank_confirmation__isnull=True,
        )
        .order_by("pk")
    )

    for payment in unconfirmed:
        exceptions.append({
            "kind": "CUSTOMER_VERIFIED_BANK_UNCONFIRMED",
            "record_id": str(payment.pk),
            "amount": str(payment.amount),
            "review_date": payment.received_date.isoformat(),
            "review_date_type": "RECEIVED_DATE_NOT_BANK_CONFIRMATION",
            "cash_settlement_verified": False,
            "reason": (
                "Verified customer payment has no bank-availability "
                "confirmation. It cannot enter supported cash receipts."
            ),
        })

    # The payment-period end selects records for REVIEW only.
    # It must never be used as a cash settlement date.
    contractor_records = (
        ContractorPaymentRecord.objects
        .filter(
            status=ContractorPaymentRecord.Status.APPROVED,
            payment_period_end__range=(start, end),
        )
        .order_by("pk")
    )

    for record in contractor_records:
        issuance = ContractorPaymentIssuance.objects.filter(
            payment_record_id=record.pk
        ).first()
        verification = (
            ContractorPaymentSettlementVerification.objects
            .filter(payment_record_id=record.pk)
            .first()
        )

        if issuance is None:
            kind = "CONTRACTOR_APPROVED_NOT_ISSUED"
            reason = "Approved contractor payment lacks issuance evidence."
        elif verification is None:
            kind = "CONTRACTOR_ISSUED_NOT_SETTLED"
            reason = "Issued contractor payment lacks verified settlement."
        else:
            kind = "CONTRACTOR_VERIFIED_NOT_MARKED_PAID"
            reason = (
                "Contractor settlement is recorded but the payment "
                "has not completed the Paid transition."
            )

        exceptions.append({
            "kind": kind,
            "record_id": str(record.pk),
            "amount": str(record.final_amount),
            "review_date": record.payment_period_end.isoformat(),
            "review_date_type": "PAYMENT_PERIOD_END_NOT_SETTLEMENT",
            "cash_settlement_verified": False,
            "reason": reason,
        })

    keys = [(item["kind"], item["record_id"]) for item in exceptions]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate evidence exception detected.")

    return {
        "review_start": start.isoformat(),
        "review_end": end.isoformat(),
        "partial_cash": cash,
        "exceptions": exceptions,
        "exception_count": len(exceptions),
        "review_dates_are_not_cash_dates": True,
        "missing_bank_ledger": True,
        "missing_opening_balances": True,
        "missing_other_cash_movements": True,
        "inventory_complete": False,
        "bank_reconciled": False,
        "financial_statement_ready": False,
        "financial_statement_certified": False,
        "operational_changes_performed": False,
    }
