"""Test-only candidate customer full-payment receipt date.

Requires verified, audited receipts and bank availability confirmations.
Approved refunds/reversals, conflicting MSRs, incomplete or mismatched
evidence fail closed. This is NOT a final earning-date determination:
historical MSR revisions, later adjustments, backdated verification,
bank-availability timing and audit-chain validation still need review.

Never use this candidate for live payroll, compensation accrual or access.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.utils import timezone

from .models import (
    AuditEvent,
    CustomerPayment,
    CustomerPaymentAdjustment,
    CustomerPaymentBankConfirmation,
    Project,
)


def _uuid(value):
    try:
        if isinstance(value, bool):
            return None
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _one_event(entity_id, action):
    events = list(AuditEvent.objects.filter(
        entity_id=entity_id, action=action
    ))
    if len(events) != 1 or type(events[0].payload) is not dict:
        return None
    return events[0]


def candidate_full_customer_receipt_date(*, project_id):
    """Return a provisional receipt date, never an access decision."""
    project_uuid = _uuid(project_id)
    if project_uuid is None:
        return None

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_uuid).first()

    if project is None or project.state == "CANCELLED":
        return None

    msr = project.current_approved
    if msr is None or msr.status != "APPROVED":
        return None

    try:
        total = Decimal(str(msr.snapshot["total_price"]))
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return None

    if not total.is_finite() or total <= Decimal("0.00"):
        return None

    payments = list(CustomerPayment.objects.filter(
        project_id=project_uuid,
        status=CustomerPayment.Status.VERIFIED,
    ).order_by("received_date", "pk"))

    if not payments:
        return None

    if CustomerPaymentAdjustment.objects.filter(
        payment__project_id=project_uuid,
        status=CustomerPaymentAdjustment.Status.APPROVED,
    ).exists():
        # Historical adjustment timing is not yet independently resolved.
        return None

    today = timezone.localdate()
    balance = Decimal("0.00")
    first_full_date = None

    for payment in payments:
        if payment.msr_id != msr.pk:
            return None
        if payment.amount <= 0 or not payment.amount.is_finite():
            return None
        if type(payment.received_date) is not date:
            return None
        if payment.received_date > today:
            return None
        if payment.verified_by_id is None or payment.verified_at is None:
            return None
        if not payment.payment_reference or not payment.payment_reference.strip():
            return None

        verification = _one_event(
            payment.pk, "customer.payment.verified"
        )
        if verification is None:
            return None

        expected_verification = {
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "payment_reference": payment.payment_reference,
            "amount": str(payment.amount),
            "approved_total": str(total),
        }

        if verification.actor_id != payment.verified_by_id:
            return None
        if any(
            verification.payload.get(key) != value
            for key, value in expected_verification.items()
        ):
            return None

        confirmation = CustomerPaymentBankConfirmation.objects.filter(
            payment_id=payment.pk
        ).first()
        if confirmation is None:
            return None
        if confirmation.confirmation_date < payment.received_date:
            return None
        if confirmation.confirmation_date > today:
            return None
        if confirmation.confirmed_at < payment.verified_at:
            return None

        bank_audit = _one_event(
            confirmation.pk,
            "customer.payment.bank_availability.confirmed",
        )
        if bank_audit is None:
            return None

        expected_bank = {
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "payment_id": str(payment.pk),
            "payment_reference": payment.payment_reference,
            "payment_amount": str(payment.amount),
            "bank_reference": confirmation.bank_reference,
            "confirmation_date": confirmation.confirmation_date.isoformat(),
            "confirmation_method": confirmation.confirmation_method,
            "confirmation_note": confirmation.confirmation_note,
            "confirmed_at": confirmation.confirmed_at.isoformat(),
        }

        if bank_audit.actor_id != confirmation.confirmed_by_id:
            return None
        if bank_audit.sequence <= verification.sequence:
            return None
        if any(
            bank_audit.payload.get(key) != value
            for key, value in expected_bank.items()
        ):
            return None

        balance += payment.amount
        if first_full_date is None and balance >= total:
            first_full_date = payment.received_date

    return first_full_date


def customer_earning_candidate_grants_live_access(*args, **kwargs):
    """Always deny operational payroll access."""
    return False