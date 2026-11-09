"""Proposed historical payroll evidence CONTRACT, not authorization.

This validator checks the shape and consistency of evidence supplied by
future trusted services. It cannot establish database provenance,
immutability, approvals, or historical truth by itself.

Never use a caller-provided dictionary to authorize payroll disclosure.
Live payroll classification remains disabled.
"""
from datetime import date

from .models import Role


SOURCE_ROLES = {
    "PROJECT_SALES_OWNERSHIP_SNAPSHOT": Role.SALES_ASSOCIATE,
    "PROJECT_TECHNICAL_ASSIGNMENT_SNAPSHOT": Role.TECHNICIAN,
}

REQUIRED_FIELDS = frozenset({
    "source_kind",
    "subject_role",
    "subject_id",
    "project_id",
    "evidence_reference",
    "effective_date",
    "ended_date",
})


def _identifier(value):
    return type(value) is str and bool(value.strip())


def candidate_historical_role(evidence, *, subject_id, project_id, earned_on):
    """Return a candidate category only; NEVER grant effective access."""
    if type(evidence) is not dict:
        return None
    if frozenset(evidence) != REQUIRED_FIELDS:
        return None
    if not _identifier(subject_id) or not _identifier(project_id):
        return None
    if type(earned_on) is not date:
        return None

    source = evidence["source_kind"]
    if type(source) is not str or source not in SOURCE_ROLES:
        return None

    role = SOURCE_ROLES[source]
    if evidence["subject_role"] != role:
        return None

    if not all(
        _identifier(evidence[key])
        for key in ("subject_id", "project_id", "evidence_reference")
    ):
        return None

    if evidence["subject_id"] != subject_id:
        return None
    if evidence["project_id"] != project_id:
        return None

    effective = evidence["effective_date"]
    ended = evidence["ended_date"]

    if type(effective) is not date:
        return None
    if ended is not None and type(ended) is not date:
        return None
    if effective > earned_on:
        return None
    if ended is not None and ended < earned_on:
        return None
    if ended is not None and ended < effective:
        return None

    return role


def historical_payroll_live_access(*args, **kwargs):
    """No permission or disclosure until approved trusted integration."""
    return False