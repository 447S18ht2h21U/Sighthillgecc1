"""Non-executable insertion-integrity policy for user permissions.

These checks validate proposed evidence structure and relationships.
They are not proof of database existence, authenticated identity,
approval authority, audit integrity, or operational access.
"""

from .access_user_permission_evidence_design import (
    valid_request_evidence,
    valid_decision_evidence,
    valid_termination_evidence,
)


def proposed_request_insert_allowed(
    *,
    request,
    existing_decision=None,
    existing_termination=None,
):
    """A request cannot arrive with approval or termination evidence."""

    return (
        valid_request_evidence(request)
        and existing_decision is None
        and existing_termination is None
    )


def proposed_decision_insert_allowed(
    *,
    request,
    decision,
    request_exists,
    existing_decision=None,
):
    """Validate a decision without trusting claimed officer authority."""

    return (
        request_exists is True
        and existing_decision is None
        and valid_decision_evidence(request, decision)
    )


def proposed_termination_insert_allowed(
    *,
    request,
    decision,
    termination,
    request_exists,
    decision_exists,
    existing_termination=None,
):
    """Validate termination structure without executing revocation."""

    return (
        request_exists is True
        and decision_exists is True
        and existing_termination is None
        and valid_termination_evidence(request, decision, termination)
    )


def insertion_requires_trusted_authorization():
    """All future live decision and termination services must verify authority."""

    return True


def insertion_requires_atomic_audit():
    """Future evidence, audit, and outbox writes must share one transaction."""

    return True


def permission_insertion_executed(*args, **kwargs):
    """No database insertion or access activation is implemented here."""

    return False