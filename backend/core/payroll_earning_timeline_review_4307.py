"""Test-only review of historical compensation earning-date chronology.

The customer receipt date and the bank availability date are distinct.
This report can identify a timing difference; it cannot authorize
a payroll earning date, access, payment, or compensation calculation.

Full historical MSR reconciliation, refund timing and complete audit-chain
verification remain unresolved. Never register as a live payroll API.
"""
from datetime import date

from .models import CustomerPayment, CustomerPaymentBankConfirmation
from .payroll_technical_provenance_4296 import _uuid
from .payroll_earning_lineage_4306 import candidate_earning_lineage


def _date_issue(received_date, bank_date):
    if type(received_date) is not date or type(bank_date) is not date:
        return "INVALID_DATE"
    if bank_date < received_date:
        return "BANK_DATE_BEFORE_RECEIPT"
    if bank_date > received_date:
        return "BANK_AVAILABLE_AFTER_RECEIPT"
    return None


def candidate_earning_timeline_review(*, payment_id):
    identifier = _uuid(payment_id)
    if identifier is None:
        return None

    lineage = candidate_earning_lineage(payment_id=identifier)
    if lineage is None:
        return None

    reviewed = []
    seen = set()

    for item in lineage["supporting_receipts"]:
        payment_uuid = _uuid(item.get("customer_payment_id"))
        confirmation_uuid = _uuid(item.get("bank_confirmation_id"))
        if payment_uuid is None or confirmation_uuid is None:
            return None
        if payment_uuid in seen:
            return None
        seen.add(payment_uuid)

        payment = CustomerPayment.objects.filter(
            pk=payment_uuid,
            project_id=lineage["project_id"],
        ).first()
        confirmation = CustomerPaymentBankConfirmation.objects.filter(
            pk=confirmation_uuid,
            payment_id=payment_uuid,
        ).first()

        if payment is None or confirmation is None:
            return None
        if payment.received_date.isoformat() != item["received_date"]:
            return None
        if confirmation.confirmation_date.isoformat() != item[
            "bank_confirmation_date"
        ]:
            return None

        issue = _date_issue(
            payment.received_date,
            confirmation.confirmation_date,
        )
        if issue in ("INVALID_DATE", "BANK_DATE_BEFORE_RECEIPT"):
            return None

        reviewed.append({
            "customer_payment_id": str(payment.pk),
            "received_date": payment.received_date.isoformat(),
            "bank_available_date": confirmation.confirmation_date.isoformat(),
            "timing_issue": issue,
        })

    if not reviewed:
        return None

    return {
        "payment_record_id": lineage["payment_record_id"],
        "project_id": lineage["project_id"],
        "approved_msr_id": lineage["approved_msr_id"],
        "candidate_receipt_date": lineage["candidate_receipt_date"],
        "reviewed_receipts": reviewed,
        "timing_difference_present": any(
            item["timing_issue"] is not None for item in reviewed
        ),
        "earning_date_authorized": False,
        "review_status": "HUMAN_REVIEW_REQUIRED_TEST_ONLY",
    }


def timeline_review_grants_live_access(*args, **kwargs):
    return False