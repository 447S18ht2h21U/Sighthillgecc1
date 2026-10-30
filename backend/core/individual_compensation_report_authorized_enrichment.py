"""Ownership-enforced entry points for compensation evidence enrichment.

These services are read-only and do not authorize financial changes.

The ownership-scoped query must succeed before evidence enrichment
can occur. No live API endpoint is installed by this module.
"""

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound

from .access_compensation_scope import (
    own_contractor_payment_scope,
    own_employee_payroll_scope,
)
from .individual_compensation_report_enrichment import (
    enrich_owned_contractor_payment_record,
    enrich_owned_employee_payroll_record,
)


def _owned_record_or_not_found(scope, record_id):
    """Do not distinguish missing records from records owned by others."""

    if isinstance(record_id, bool) or not isinstance(
        record_id, (UUID, str)
    ):
        raise NotFound("Compensation record not found.")

    if isinstance(record_id, str):
        if not record_id or record_id.strip() != record_id:
            raise NotFound("Compensation record not found.")
        try:
            record_id = UUID(record_id)
        except (ValueError, AttributeError):
            raise NotFound("Compensation record not found.")

    try:
        return scope.filter(pk=record_id).first()
    except (
        TypeError,
        ValueError,
        OverflowError,
        DjangoValidationError,
    ):
        raise NotFound("Compensation record not found.")


def authorized_employee_payroll_enrichment(actor, record_id):
    """Return evidence only for the actor's own employee payroll record."""

    record = _owned_record_or_not_found(
        own_employee_payroll_scope(actor),
        record_id,
    )

    if record is None:
        raise NotFound("Compensation record not found.")

    return enrich_owned_employee_payroll_record(record)


def authorized_contractor_payment_enrichment(actor, record_id):
    """Return evidence only for the actor's own contractor payment record."""

    record = _owned_record_or_not_found(
        own_contractor_payment_scope(actor),
        record_id,
    )

    if record is None:
        raise NotFound("Compensation record not found.")

    return enrich_owned_contractor_payment_record(record)