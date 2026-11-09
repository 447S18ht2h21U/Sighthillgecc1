"""Test-only integration of customer receipt and technician provenance.

A returned result is a PROVISIONAL CANDIDATE, never an earning-date
approval, compensation obligation, access grant, or payment instruction.

The separate receipt-date source has known limitations concerning
historical MSR revisions, late bank confirmation, adjusted payments,
and full audit-chain validation. Do not register this as a live API.
"""
from .models import ContractorPaymentRecord, Role
from .payroll_technical_provenance_4296 import _uuid
from .payroll_payment_technical_link_4300 import (
    candidate_technical_payment_link,
)
from .payroll_customer_earning_evidence_4303 import (
    candidate_full_customer_receipt_date,
)


def candidate_earned_technical_payment(*, payment_id):
    """Reconcile the SAME stored project across both evidence sources."""
    identifier = _uuid(payment_id)
    if identifier is None:
        return None

    payment = ContractorPaymentRecord.objects.filter(
        pk=identifier
    ).first()
    if payment is None or payment.project_id is None:
        return None

    candidate_date = candidate_full_customer_receipt_date(
        project_id=payment.project_id
    )
    if candidate_date is None:
        return None

    category = candidate_technical_payment_link(
        payment_id=payment.pk,
        earned_on=candidate_date,
    )
    if category != Role.TECHNICIAN:
        return None

    return {
        "payment_record_id": str(payment.pk),
        "project_id": str(payment.project_id),
        "candidate_role": Role.TECHNICIAN,
        "candidate_receipt_date": candidate_date.isoformat(),
        "status": "TEST_ONLY_UNAPPROVED_CANDIDATE",
    }


def earned_technical_candidate_grants_live_access(*args, **kwargs):
    """No caller or result may enable a live payroll disclosure."""
    return False