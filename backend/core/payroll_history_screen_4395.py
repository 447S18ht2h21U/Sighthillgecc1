"""VERIDIAN 1907P-4395: fictional Payment History adapter.

Pure, test-only presentation formatting. Never a permission gate.
No Django model access, database queries, payment actions or APIs.
Recorded PAID, issuance and settlement candidate evidence are NOT
independent proof of an actual paid date.
"""

import re
from datetime import date

_ID = re.compile(r"TEST-[A-Z0-9-]{1,30}\Z")
_NAME = re.compile(r"Fictional [A-Za-z ]{1,60}\Z")
_AMOUNT = re.compile(r"-?(?:0|[1-9][0-9]{0,11})\.[0-9]{2}\Z")
_MAX_CENTS = 9007199254740991


def _id(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("Synthetic TEST reference required.")
    return value


def _date(value):
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("Invalid historical date.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid historical date.") from None
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical historical date.")
    return value


def _amount(value, kind):
    if type(value) is not str or _AMOUNT.fullmatch(value) is None:
        raise ValueError("Exact two-decimal amount required.")
    if value.startswith("-") and kind != "ADJUSTMENT":
        raise ValueError("Negative normal compensation prohibited.")
    if abs(int(value.replace(".", ""))) > _MAX_CENTS:
        raise ValueError("Unsafe historical amount.")
    return value


def format_fictional_payment_history_4395(source):
    """Allowlist fictional payment history for presentation only."""
    if type(source) is not dict:
        raise ValueError("Fictional history collection required.")

    if source.get("view") != "fictional_payment_history_only":
        raise ValueError("Unexpected Payment History view.")

    for flag in (
        "backend_scope_verified",
        "external_payment_evidence_verified",
        "live_payment_authorized",
        "payment_actions_authorized",
    ):
        if source.get(flag) is not False:
            raise ValueError("Operational payroll authority prohibited.")

    rows = source.get("rows")
    if type(rows) is not list or len(rows) > 100:
        raise ValueError("Invalid fictional history collection.")

    result = []
    references = set()

    for raw in rows:
        if type(raw) is not dict:
            raise ValueError("Invalid fictional history row.")

        reference = _id(raw.get("reference"))
        if reference in references:
            raise ValueError("Duplicate historical reference.")
        references.add(reference)

        recipient = raw.get("recipient")
        if type(recipient) is not str or _NAME.fullmatch(recipient) is None:
            raise ValueError("Fictional recipient required.")

        category = raw.get("category")
        kind = raw.get("kind")
        status = raw.get("recorded_status")

        if category not in ("employee", "contractor"):
            raise ValueError("Invalid history category.")
        if kind not in ("COMPENSATION", "ADJUSTMENT"):
            raise ValueError("Invalid compensation kind.")
        if status not in ("DRAFT", "APPROVED", "PAID"):
            raise ValueError("Invalid recorded payment status.")

        adjustment_of = raw.get("adjustment_of")
        if kind == "ADJUSTMENT":
            adjustment_of = _id(adjustment_of)
            if adjustment_of == reference:
                raise ValueError("Self-referencing adjustment.")
        elif adjustment_of is not None:
            raise ValueError("Normal compensation cannot be an adjustment.")

        period_start = _date(raw.get("period_start"))
        period_end = _date(raw.get("period_end"))

        if not period_start or not period_end or period_start > period_end:
            raise ValueError("Invalid history period.")

        compensation_date = _date(raw.get("compensation_date"))
        proposed = _date(raw.get("proposed_payment_date"))
        issued = _date(raw.get("issued_date"))
        settlement = _date(raw.get("settlement_candidate_date"))

        method = raw.get("method")
        payment_reference = raw.get("payment_reference")

        if method is not None and method not in ("ACH", "CHECK"):
            raise ValueError("Unsupported fictional payment method.")

        if payment_reference is not None:
            payment_reference = _id(payment_reference)

        if issued is None:
            if method is not None or payment_reference is not None:
                raise ValueError("Issuance metadata without issuance.")
            if settlement is not None:
                raise ValueError("Settlement without issuance.")
        else:
            if method is None or payment_reference is None or status != "PAID":
                raise ValueError("Conflicting payment issuance evidence.")

        if settlement is not None and settlement < issued:
            raise ValueError("Settlement candidate precedes issuance.")

        if (
            raw.get("actual_paid_date") is not None
            or raw.get("actual_paid_date_verified") is not False
        ):
            raise ValueError("Unverified actual payment date prohibited.")

        if type(raw.get("exception")) is not bool:
            raise ValueError("Explicit exception flag required.")

        result.append({
            "reference": reference,
            "recipient": recipient,
            "category": category,
            "kind": kind,
            "adjustment_of": adjustment_of,
            "compensation_date": compensation_date,
            "period_start": period_start,
            "period_end": period_end,
            "amount": _amount(raw.get("amount"), kind),
            "recorded_status": status,
            "proposed_payment_date": proposed,
            "issued_date": issued,
            "settlement_candidate_date": settlement,
            "method": method,
            "payment_reference": payment_reference,
            "actual_paid_date": None,
            "actual_paid_date_verified": False,
            "exception": raw["exception"],
        })

    return {
        "view": "fictional_payment_history_only",
        "backend_scope_verified": False,
        "external_payment_evidence_verified": False,
        "live_payment_authorized": False,
        "payment_actions_authorized": False,
        "rows": result,
    }


def history_screen_4395_grants_live_access():
    return False
