"""VERIDIAN 4412: proposed financial statement review conditions.

Isolated synthetic evidence only. NOT a production permission gate,
accounting engine, financial statement or approval service.
"""

from decimal import Decimal, InvalidOperation
import re

_MONEY = re.compile(r"-?(?:0|[1-9][0-9]{0,11})\.[0-9]{2}\Z")


def _amount(value):
    if type(value) is not str or not _MONEY.fullmatch(value):
        raise ValueError("Exact two-decimal financial amount required.")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid financial amount.") from None


def _record(value):
    if type(value) is not dict:
        raise ValueError("Structured financial evidence required.")
    return value


def assess_balance_sheet_4412(data):
    """Check arithmetic only; does not certify account completeness."""
    data = _record(data)
    assets = _amount(data.get("assets"))
    liabilities = _amount(data.get("liabilities"))
    equity = _amount(data.get("equity"))
    if assets != liabilities + equity:
        raise ValueError("Balance sheet does not balance.")
    return {
        "arithmetically_balanced": True,
        "account_completeness_verified": False,
        "operationally_approved": False,
    }


def assess_cash_flow_4412(data):
    """Require external proof for each synthetic cash movement."""
    data = _record(data)
    movements = data.get("movements")
    if type(movements) is not list or len(movements) > 100:
        raise ValueError("Cash movements must be explicitly listed.")

    total = Decimal("0.00")
    references = set()

    for raw in movements:
        entry = _record(raw)
        reference = entry.get("reference")
        if (type(reference) is not str or
            not re.fullmatch(r"TEST-[A-Z0-9-]{1,36}", reference) or
            reference in references):
            raise ValueError("Unique synthetic cash reference required.")
        references.add(reference)

        if entry.get("independently_verified") is not True:
            raise ValueError("Cash movement evidence is unverified.")

        if entry.get("kind") not in ("RECEIPT", "DISBURSEMENT"):
            raise ValueError("Invalid cash movement kind.")

        amount = _amount(entry.get("amount"))
        if amount < 0:
            raise ValueError("Cash movement amount cannot be negative.")

        total += (
            amount if entry["kind"] == "RECEIPT" else -amount
        )

    expected = _amount(data.get("reported_net_cash_flow"))
    if total != expected:
        raise ValueError("Cash flow does not reconcile.")

    return {
        "synthetic_movements_reconciled": True,
        "net_cash_flow": str(total),
        "bank_reconciliation_verified": False,
        "operationally_approved": False,
    }


def assess_separate_review_4412(data):
    """Proposed independence check, not an approved role policy."""
    data = _record(data)
    creator = data.get("creator_id")
    reviewer = data.get("reviewer_id")

    if (type(creator) is not str or
        type(reviewer) is not str or
        not re.fullmatch(r"TEST-[A-Z0-9-]{1,36}", creator) or
        not re.fullmatch(r"TEST-[A-Z0-9-]{1,36}", reviewer) or
        creator == reviewer):
        raise ValueError("Independent synthetic reviewer required.")

    return {
        "different_reviewers": True,
        "corporate_approval_policy_confirmed": False,
        "operationally_approved": False,
    }
