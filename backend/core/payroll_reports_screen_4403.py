"""VERIDIAN 1907P-4403: isolated fictional payroll reports.

Presentation only. No Django ORM, actual financial records,
scope authorization, verified bank evidence, payments or exports.
Approval indicators are fictional and are NOT audit evidence.
"""

import re
from datetime import date, timedelta

_REFERENCE = re.compile(r"TEST-[A-Z0-9-]{1,36}\Z")
_RECIPIENT = re.compile(r"Fictional [A-Za-z ]{1,60}\Z")
_AMOUNT = re.compile(r"-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}\Z")

_STATUSES = ("DRAFT", "APPROVED", "PAID_RECORDED")
_KINDS = ("COMPENSATION", "ADJUSTMENT")
_CATEGORIES = ("employee", "contractor")


def _identifier(value):
    if type(value) is not str or _REFERENCE.fullmatch(value) is None:
        raise ValueError("Synthetic TEST reference required.")
    return value


def _date(value):
    if type(value) is not str:
        raise ValueError("ISO report date required.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid report date.") from None
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical report date.")
    return parsed


def _money(value, adjustment):
    if type(value) is not str or _AMOUNT.fullmatch(value) is None:
        raise ValueError("Invalid exact report amount.")
    if value.startswith("-") and not adjustment:
        raise ValueError("Negative compensation prohibited.")
    return value


def format_fictional_payroll_reports_4403(source):
    """Map explicitly allowlisted fictional company payroll fields."""
    if type(source) is not dict:
        raise ValueError("Fictional payroll report required.")

    if source.get("view") != "fictional_company_payroll_report_only":
        raise ValueError("Unsupported payroll report view.")

    for flag in (
        "backend_scope_verified",
        "external_payment_evidence_verified",
        "exports_available",
        "live_payroll_authorized",
    ):
        if source.get(flag) is not False:
            raise ValueError("Live reporting authority prohibited.")

    start = _date(source.get("period_start"))
    end = _date(source.get("period_end"))

    if (
        start.weekday() != 0
        or end.weekday() != 6
        or end - start != timedelta(days=6)
    ):
        raise ValueError("Payroll reporting must cover Monday-Sunday.")

    rows = source.get("rows")
    if type(rows) is not list or len(rows) > 100:
        raise ValueError("Invalid payroll report rows.")

    output = []
    references = {}

    for raw in rows:
        if type(raw) is not dict:
            raise ValueError("Fictional report record required.")

        reference = _identifier(raw.get("reference"))
        if reference in references:
            raise ValueError("Duplicate payroll report reference.")

        recipient = raw.get("recipient")
        if (
            type(recipient) is not str
            or _RECIPIENT.fullmatch(recipient) is None
        ):
            raise ValueError("Fictional recipient required.")

        category = raw.get("category")
        kind = raw.get("kind")
        status = raw.get("recorded_status")

        if category not in _CATEGORIES or type(category) is not str:
            raise ValueError("Invalid payroll category.")
        if kind not in _KINDS or type(kind) is not str:
            raise ValueError("Invalid payroll obligation type.")
        if status not in _STATUSES or type(status) is not str:
            raise ValueError("Invalid recorded status.")

        adjustment = kind == "ADJUSTMENT"
        adjustment_of = raw.get("adjustment_of")

        if adjustment:
            adjustment_of = _identifier(adjustment_of)
            if adjustment_of == reference or status != "DRAFT":
                raise ValueError("Unverified adjustment state invalid.")
        elif adjustment_of is not None:
            raise ValueError("Compensation cannot replace original.")

        first = raw.get("first_approval_recorded")
        final = raw.get("comptroller_approval_recorded")
        audit = raw.get("audit_recorded")
        exception = raw.get("exception")

        if any(type(value) is not bool for value in
               (first, final, audit, exception)):
            raise ValueError("Explicit approval flags required.")

        approved = status != "DRAFT"
        if approved and not (first and final and audit):
            raise ValueError("Approved obligation lacks evidence flags.")
        if not approved and (first or final or audit):
            raise ValueError("Draft obligation claims approval.")

        if (
            raw.get("independently_verified_paid_date") is not None
            or raw.get("independently_verified_paid") is not False
        ):
            raise ValueError("Independent payment evidence unavailable.")

        item = {
            "reference": reference,
            "recipient": recipient,
            "category": category,
            "kind": kind,
            "adjustment_of": adjustment_of,
            "amount": _money(raw.get("amount"), adjustment),
            "recorded_status": status,
            "first_approval_recorded": first,
            "comptroller_approval_recorded": final,
            "audit_recorded": audit,
            "independently_verified_paid_date": None,
            "independently_verified_paid": False,
            "exception": exception,
        }
        output.append(item)
        references[reference] = item

    for item in output:
        if item["kind"] != "ADJUSTMENT":
            continue
        original = references.get(item["adjustment_of"])
        if (
            original is None
            or original["kind"] != "COMPENSATION"
            or original["recipient"] != item["recipient"]
            or original["category"] != item["category"]
        ):
            raise ValueError("Adjustment original does not match.")

    return {
        "view": "fictional_company_payroll_report_only",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "backend_scope_verified": False,
        "external_payment_evidence_verified": False,
        "exports_available": False,
        "live_payroll_authorized": False,
        "rows": output,
    }


def payroll_reports_4403_grants_live_access():
    return False
