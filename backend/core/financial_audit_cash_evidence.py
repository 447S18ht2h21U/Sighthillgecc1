"""Evidence classifications for monthly cash audit review.

Pure classification only. No ORM access, financial postings, or mutations.
These classifications do not establish accounting recognition by themselves.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def _valid_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("A valid cash evidence amount is required.") from None

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Cash evidence amount must be positive and finite.")

    return amount


def _valid_date(value, label):
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(label + " must be a calendar date.")
    return value


def classify_cash_evidence(
    *,
    transaction_type,
    source_id,
    amount,
    status,
    event_date=None,
    issued=False,
    bank_verified=False,
    bank_event_date=None,
):
    """Classify supplied evidence without assuming that approval means cash.

    The caller must supply trustworthy, source-validated evidence. This
    function does not authenticate or independently verify that evidence.
    """

    valid_types = {
        "CUSTOMER_RECEIPT",
        "CONTRACTOR_PAYMENT",
        "EMPLOYEE_PAYROLL",
        "COMMISSION",
        "CUSTOMER_ADJUSTMENT",
    }

    if transaction_type not in valid_types:
        raise ValueError("Unsupported cash evidence transaction type.")

    if not isinstance(source_id, (str, int)) or not str(source_id).strip():
        raise ValueError("A source-record identifier is required.")

    amount = _valid_amount(amount)

    if not isinstance(status, str) or not status.strip():
        raise ValueError("A source-record status is required.")

    if type(issued) is not bool or type(bank_verified) is not bool:
        raise ValueError("Evidence flags must be boolean.")

    if event_date is not None:
        _valid_date(event_date, "Event date")

    if bank_event_date is not None:
        _valid_date(bank_event_date, "Bank evidence date")

    if bank_verified and bank_event_date is None:
        raise ValueError("Verified bank evidence requires its event date.")

    if not bank_verified and bank_event_date is not None:
        raise ValueError(
            "Bank evidence date requires verified bank evidence."
        )

    classification = "NOT_CASH_VERIFIED"
    recognized_as_bank_verified = False

    if transaction_type == "CUSTOMER_RECEIPT":
        if status not in {"PENDING", "VERIFIED", "REJECTED"}:
            raise ValueError("Invalid customer receipt status.")
        if issued:
            raise ValueError(
                "Customer receipts cannot use payment issuance evidence."
            )
        if bank_verified and status != "VERIFIED":
            raise ValueError("Bank confirmation requires a verified receipt.")
        if bank_verified and event_date is None:
            raise ValueError(
                "Bank-confirmed receipt requires its received date."
            )
        if bank_verified and event_date is not None and bank_event_date < event_date:
            raise ValueError("Bank availability cannot predate receipt.")
        if bank_verified:
            classification = "BANK_AVAILABILITY_CONFIRMED"
            recognized_as_bank_verified = True
        elif status == "VERIFIED":
            classification = "RECEIPT_VERIFIED_BANK_UNCONFIRMED"

    elif transaction_type == "CONTRACTOR_PAYMENT":
        if status not in {"DRAFT", "APPROVED", "PAID"}:
            raise ValueError("Invalid contractor payment status.")
        if status == "DRAFT" and issued:
            raise ValueError("Draft contractor payment cannot be issued.")
        if bank_verified and (not issued or status not in {"APPROVED", "PAID"}):
            raise ValueError("Contractor bank verification requires issuance.")
        if status == "PAID" and (not issued or not bank_verified):
            raise ValueError(
                "Paid contractor payment requires issuance and settlement."
            )
        if bank_verified:
            classification = "INDEPENDENT_SETTLEMENT_VERIFIED"
            recognized_as_bank_verified = True
        elif status == "PAID":
            classification = "RECORDED_PAID_SETTLEMENT_UNVERIFIED"
        elif issued:
            classification = "ISSUED_SETTLEMENT_UNVERIFIED"
        elif status == "APPROVED":
            classification = "APPROVED_NOT_ISSUED"

    elif transaction_type == "EMPLOYEE_PAYROLL":
        if status not in {"DRAFT", "APPROVED", "PAID"}:
            raise ValueError("Invalid employee payroll status.")
        if bank_verified:
            raise ValueError(
                "Independent employee settlement is not established by this workflow."
            )
        if status == "DRAFT" and issued:
            raise ValueError("Draft employee payroll cannot be issued.")
        if status == "PAID" and not issued:
            raise ValueError(
                "Paid employee payroll requires payment issuance."
            )
        if status == "PAID":
            classification = "RECORDED_PAID_BANK_UNVERIFIED"
        elif issued:
            classification = "ISSUED_BANK_UNVERIFIED"
        elif status == "APPROVED":
            classification = "APPROVED_NOT_ISSUED"

    elif transaction_type == "COMMISSION":
        if status not in {"DRAFT", "APPROVED"}:
            raise ValueError("Invalid commission status.")
        if issued or bank_verified:
            raise ValueError(
                "Commission issuance and settlement evidence are not implemented."
            )
        if status == "APPROVED":
            classification = "APPROVED_PAYMENT_NOT_ESTABLISHED"

    elif transaction_type == "CUSTOMER_ADJUSTMENT":
        if status not in {"PENDING", "APPROVED", "REJECTED"}:
            raise ValueError("Invalid customer adjustment status.")
        if issued or bank_verified:
            raise ValueError(
                "Adjustment settlement evidence is not implemented."
            )
        if status == "APPROVED":
            classification = "APPROVED_ADJUSTMENT_SETTLEMENT_UNVERIFIED"

    return {
        "transaction_type": transaction_type,
        "source_id": str(source_id),
        "amount": str(amount),
        "source_status": status,
        "event_date": event_date.isoformat() if event_date else None,
        "bank_event_date": (
            bank_event_date.isoformat() if bank_event_date else None
        ),
        "classification": classification,
        "bank_evidence_supplied": recognized_as_bank_verified,
        "accounting_recognition_determined": False,
        "cash_flow_statement_reconciled": False,
    }
