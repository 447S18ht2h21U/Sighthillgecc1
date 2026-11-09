"""Test-only VERIDIAN cash evidence classification.

All inputs are synthetic. This does not read Django models,
verify a bank ledger, authorize payments, or create financial reports.
"""

from datetime import date
from decimal import Decimal, InvalidOperation


def money(value):
    if type(value) is not str:
        raise ValueError("Exact string monetary amount required.")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid amount.") from None
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent != -2:
        raise ValueError("Nonnegative two-decimal amount required.")
    return amount


def cash_evidence_review_4419(movements, start, end):
    if type(start) is not date or type(end) is not date or start > end:
        raise ValueError("Valid report period required.")
    if type(movements) is not list or len(movements) > 100:
        raise ValueError("Explicit, limited evidence list required.")

    included = []
    withheld = []
    seen = set()
    net = Decimal("0.00")

    for item in movements:
        if type(item) is not dict:
            raise ValueError("Structured evidence required.")
        ref = item.get("reference")
        if (
            type(ref) is not str
            or not ref.startswith("TEST-")
            or len(ref) > 45
            or ref in seen
        ):
            raise ValueError("Unique synthetic evidence reference required.")
        seen.add(ref)

        kind = item.get("kind")
        if kind not in (
            "CUSTOMER_RECEIPT", "CONTRACTOR_SETTLEMENT",
            "EMPLOYEE_ISSUANCE", "CUSTOMER_ADJUSTMENT",
            "APPROVED_COMMISSION"
        ):
            raise ValueError("Unsupported cash evidence kind.")

        amount = money(item.get("amount"))
        evidence_date = item.get("date")
        if type(evidence_date) is not date:
            raise ValueError("Explicit cash evidence date required.")

        reason = None
        direction = None

        if kind == "CUSTOMER_RECEIPT":
            if (
                item.get("customer_status") == "VERIFIED"
                and item.get("bank_confirmed") is True
                and item.get("independently_verified") is True
            ):
                direction = 1
            else:
                reason = "Customer bank receipt evidence incomplete"

        elif kind == "CONTRACTOR_SETTLEMENT":
            if (
                item.get("payment_status") == "PAID"
                and item.get("settlement_verified") is True
                and item.get("independently_verified") is True
            ):
                direction = -1
            else:
                reason = "Contractor settlement evidence incomplete"

        elif kind == "EMPLOYEE_ISSUANCE":
            reason = "Issuance alone does not prove cleared payroll"

        elif kind == "CUSTOMER_ADJUSTMENT":
            reason = "Approved refund or reversal lacks settlement proof"

        else:
            reason = "Commission approval is not a disbursement"

        if not start <= evidence_date <= end:
            reason = "Outside selected accounting period"
            direction = None

        if direction is None:
            withheld.append({"reference": ref, "reason": reason})
        else:
            net += amount * direction
            included.append(ref)

    return {
        "supported_test_cash_flow": str(net),
        "included_references": included,
        "withheld": withheld,
        "bank_reconciled": False,
        "financial_statement_certified": False,
        "operational_records_accessed": False,
    }
