"""Test-only evidence lineage for a proposed historical earning date.

Returns the exact MSR and receipt/bank-confirmation identifiers used
by the conservative candidate rules. Not an immutable earning-date
certificate, verified complete audit chain, or payroll permission.
Never expose as an operational endpoint without further safeguards.
"""
from decimal import Decimal, InvalidOperation

from .models import (
    ContractorPaymentRecord,
    CustomerPayment,
    CustomerPaymentBankConfirmation,
    Project,
)
from .payroll_technical_provenance_4296 import _uuid
from .payroll_msr_version_guard_4305 import (
    candidate_version_guarded_technical_payment,
)


def candidate_earning_lineage(*, payment_id):
    identifier = _uuid(payment_id)
    if identifier is None:
        return None

    candidate = candidate_version_guarded_technical_payment(
        payment_id=identifier
    )
    if candidate is None:
        return None

    record = ContractorPaymentRecord.objects.filter(
        pk=identifier
    ).first()
    if record is None or record.project_id is None:
        return None

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=record.project_id).first()
    if project is None or project.current_approved is None:
        return None

    msr = project.current_approved

    try:
        total = Decimal(str(msr.snapshot["total_price"]))
    except (TypeError, ValueError, KeyError, InvalidOperation):
        return None

    if not total.is_finite() or total <= 0:
        return None

    candidate_date = candidate["candidate_receipt_date"]

    payments = list(
        CustomerPayment.objects.filter(
            project_id=project.pk,
            status=CustomerPayment.Status.VERIFIED,
        ).order_by("received_date", "pk")
    )
    if not payments:
        return None

    receipts = []
    seen_references = set()
    received_through_date = Decimal("0.00")
    received_before_date = Decimal("0.00")

    for payment in payments:
        if payment.msr_id != msr.pk:
            return None

        if payment.payment_reference in seen_references:
            return None
        seen_references.add(payment.payment_reference)

        confirmation = CustomerPaymentBankConfirmation.objects.filter(
            payment_id=payment.pk
        ).first()

        if confirmation is None:
            return None

        if payment.received_date.isoformat() <= candidate_date:
            received_through_date += payment.amount

        if payment.received_date.isoformat() < candidate_date:
            received_before_date += payment.amount

        receipts.append({
            "customer_payment_id": str(payment.pk),
            "received_date": payment.received_date.isoformat(),
            "amount": str(payment.amount),
            "payment_reference": payment.payment_reference,
            "bank_confirmation_id": str(confirmation.pk),
            "bank_confirmation_date": confirmation.confirmation_date.isoformat(),
        })

    if received_before_date >= total:
        return None
    if received_through_date < total:
        return None

    if candidate["project_id"] != str(project.pk):
        return None
    if candidate["payment_record_id"] != str(record.pk):
        return None

    return {
        **candidate,
        "approved_msr_id": str(msr.pk),
        "approved_msr_version": msr.number,
        "approved_total": str(total),
        "supporting_receipts": receipts,
        "evidence_status": "TEST_ONLY_TRACE_NOT_FINAL_AUTHORITY",
    }


def earning_lineage_grants_live_access(*args, **kwargs):
    return False