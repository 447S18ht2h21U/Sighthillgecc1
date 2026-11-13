"""Read-only financial evidence for approved Final Customer Receipts.

This service neither creates a Receipt nor verifies email delivery.
A CEO installation exception is never counted as customer payment.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework.exceptions import ValidationError

from .installation_payment_readiness import installation_payment_readiness


CENT = Decimal("0.01")


@dataclass(frozen=True)
class FinalReceiptFinancialEvidence:
    project_id: str
    approved_msr_id: str
    approved_msr_version: int
    contract_total: Decimal
    bank_confirmed_gross: Decimal
    approved_adjustments: Decimal
    verified_customer_funds: Decimal
    outstanding_balance: Decimal
    payment_fully_confirmed: bool
    overpayment_requires_review: bool
    installation_exception_present: bool
    receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    project_completion_authorized: bool = False


def _money(value, label):
    if isinstance(value, bool):
        raise ValidationError(f"Invalid {label}.")

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"Invalid {label}.") from None

    if not amount.is_finite() or amount < 0:
        raise ValidationError(f"Invalid {label}.")

    if amount != amount.quantize(CENT):
        raise ValidationError(f"Invalid {label} precision.")

    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def assess_final_receipt_finances(project, payment_report=None):
    """Read approved MSR and independently bank-confirmed funds.

    Caller must separately enforce project access permissions.
    Passing this assessment never authorizes Receipt generation.
    """

    if project is None or getattr(project, "pk", None) is None:
        raise ValidationError("Persisted project required.")

    if getattr(project, "state", None) == "CANCELLED":
        raise ValidationError("Cancelled projects cannot issue Receipts.")

    msr = getattr(project, "current_approved", None)

    if (
        msr is None
        or getattr(msr, "status", None) != "APPROVED"
        or getattr(msr, "project_id", None) != project.pk
        or not isinstance(getattr(msr, "snapshot", None), dict)
    ):
        raise ValidationError("Current approved MSR required.")

    if payment_report is None:
        payment_report = installation_payment_readiness(project)

    if not isinstance(payment_report, dict):
        raise ValidationError("Invalid payment evidence report.")

    if (
        payment_report.get("project_id") != str(project.pk)
        or payment_report.get("msr_id") != str(msr.pk)
        or payment_report.get("msr_version") != msr.number
    ):
        raise ValidationError("Payment evidence binding mismatch.")

    contract_total = _money(
        msr.snapshot.get("total_price"), "approved contract total"
    )

    report_total = _money(
        payment_report.get("approved_total"), "payment report total"
    )

    if contract_total <= 0 or contract_total != report_total:
        raise ValidationError("Approved price and payment report differ.")

    gross = _money(
        payment_report.get("bank_confirmed_total"),
        "bank-confirmed funds",
    )
    adjustments = _money(
        payment_report.get("approved_adjustments"),
        "approved payment adjustments",
    )
    qualifying = _money(
        payment_report.get("qualifying_funds"),
        "qualifying customer funds",
    )

    expected = max(gross - adjustments, Decimal("0.00"))

    if qualifying != expected:
        raise ValidationError("Verified funds calculation mismatch.")

    outstanding = max(contract_total - qualifying, Decimal("0.00"))
    overpayment = qualifying > contract_total

    return FinalReceiptFinancialEvidence(
        project_id=str(project.pk),
        approved_msr_id=str(msr.pk),
        approved_msr_version=msr.number,
        contract_total=contract_total,
        bank_confirmed_gross=gross,
        approved_adjustments=adjustments,
        verified_customer_funds=qualifying,
        outstanding_balance=outstanding,
        payment_fully_confirmed=(
            qualifying == contract_total and not overpayment
        ),
        overpayment_requires_review=overpayment,
        installation_exception_present=(
            payment_report.get("ceo_exception_valid") is True
        ),
    )
