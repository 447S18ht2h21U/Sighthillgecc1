"""VERIDIAN 1907P-4399: fictional contractor presentation.

Database-free, test-only formatter. No actual W-9 files, license
images, agreements, private identities, onboarding activation,
permission grants, operational APIs or financial actions.

Fictional document statuses do not prove document custody.
"""

import re
from datetime import date

_REF = re.compile(r"TEST-[A-Z0-9-]{1,36}\Z")
_CONTRACTOR = re.compile(r"TEST-CTR-[A-Z0-9-]{1,24}\Z")
_NAME = re.compile(r"Fictional Contractor [A-Za-z ]{1,45}\Z")
_EVIDENCE = ("PENDING", "APPROVED", "REJECTED")
_STATES = ("PENDING", "ACTIVE", "ENDED")


def _text(value, pattern):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError("Invalid fictional contractor identifier.")
    return value


def _date(value, optional=False):
    if value is None and optional:
        return None
    if type(value) is not str:
        raise ValueError("Fictional engagement date required.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid engagement date.") from None
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical engagement date.")
    return value


def format_fictional_contractor_screen_4399(source):
    """Return an explicit safe-field allowlist for synthetic data."""
    if type(source) is not dict:
        raise ValueError("Fictional contractor collection required.")

    if source.get("view") != "fictional_contractor_records_only":
        raise ValueError("Unexpected contractor review view.")

    for flag in (
        "backend_access_verified",
        "onboarding_authority_granted",
        "live_payroll_authorized",
        "payment_actions_authorized",
    ):
        if source.get(flag) is not False:
            raise ValueError("Live authority claims are prohibited.")

    rows = source.get("rows")
    if type(rows) is not list or len(rows) > 100:
        raise ValueError("Invalid fictional engagement collection.")

    output = []
    by_reference = {}

    for raw in rows:
        if type(raw) is not dict:
            raise ValueError("Fictional engagement object required.")

        reference = _text(raw.get("reference"), _REF)

        if reference in by_reference:
            raise ValueError("Duplicate engagement reference.")

        contractor_id = _text(
            raw.get("contractor_id"), _CONTRACTOR
        )
        display_name = _text(raw.get("display_name"), _NAME)

        status = raw.get("engagement_status")
        if status not in _STATES:
            raise ValueError("Invalid engagement state.")

        start = _date(raw.get("start_date"))
        end = _date(raw.get("end_date"), optional=True)

        if end is not None and end < start:
            raise ValueError("End date precedes start date.")

        return_of = raw.get("return_of")
        if return_of is not None:
            return_of = _text(return_of, _REF)
            if return_of == reference:
                raise ValueError("Self-referencing return engagement.")

        documents = {}
        for key in ("w9", "drivers_license", "agreement"):
            value = raw.get(key)
            if type(value) is not str or value not in _EVIDENCE:
                raise ValueError("Invalid fictional document status.")
            documents[key] = value

        eligible = raw.get("payment_eligible")
        if type(eligible) is not bool:
            raise ValueError("Explicit payment eligibility required.")

        complete = all(
            value == "APPROVED" for value in documents.values()
        )

        if status == "ACTIVE":
            if not complete or end is not None or not eligible:
                raise ValueError("Unsafe fictional activation state.")
        elif eligible:
            raise ValueError("Inactive engagements cannot be eligible.")

        if status == "ENDED" and end is None:
            raise ValueError("Ended engagement needs end date.")
        if status == "PENDING" and end is not None:
            raise ValueError("Pending engagement cannot have end date.")

        result = {
            "reference": reference,
            "contractor_id": contractor_id,
            "display_name": display_name,
            "return_of": return_of,
            "engagement_status": status,
            "start_date": start,
            "end_date": end,
            "w9": documents["w9"],
            "drivers_license": documents["drivers_license"],
            "agreement": documents["agreement"],
            "payment_eligible": eligible,
        }

        by_reference[reference] = result
        output.append(result)

    for row in output:
        previous_ref = row["return_of"]
        if previous_ref is None:
            continue

        previous = by_reference.get(previous_ref)
        if (
            previous is None
            or previous["contractor_id"] != row["contractor_id"]
            or previous["engagement_status"] != "ENDED"
            or previous["end_date"] is None
            or previous["end_date"] >= row["start_date"]
        ):
            raise ValueError("Invalid historical return engagement.")

    return {
        "view": "fictional_contractor_records_only",
        "backend_access_verified": False,
        "onboarding_authority_granted": False,
        "live_payroll_authorized": False,
        "payment_actions_authorized": False,
        "rows": output,
    }


def contractor_screen_4399_grants_live_access():
    return False
