"""Test-only contractor payment and technician identity reconciliation.

A matching candidate is NOT proof of an earning date or payroll access.
The supplied earned_on value is untrusted until a separate verified
customer-payment earning-date record is implemented.

Never register as a live API or use to authorize compensation disclosure.
"""
from datetime import date

from .models import AuditEvent, ContractorPaymentRecord, Role
from .payroll_technical_provenance_4296 import _uuid
from .payroll_technical_end_provenance_4298 import (
    candidate_audited_technical_period,
)


def candidate_technical_payment_link(*, payment_id, earned_on):
    """Return only a candidate category after record consistency checks."""
    identifier = _uuid(payment_id)
    if identifier is None or type(earned_on) is not date:
        return None

    record = (
        ContractorPaymentRecord.objects
        .select_related(
            "engagement__contractor",
            "compensation_plan",
        )
        .filter(pk=identifier)
        .first()
    )
    if record is None:
        return None

    if record.status not in (
        ContractorPaymentRecord.Status.APPROVED,
        ContractorPaymentRecord.Status.PAID,
    ):
        return None

    if record.approved_by_id is None or record.approved_at is None:
        return None

    if record.project_id is None:
        return None

    if record.compensation_plan.engagement_id != record.engagement_id:
        return None

    if record.compensation_plan.status not in (
        record.compensation_plan.Status.APPROVED,
        record.compensation_plan.Status.SUPERSEDED,
    ):
        return None

    user_id = record.engagement.contractor.user_id
    if user_id is None:
        return None

    created = list(AuditEvent.objects.filter(
        entity_id=record.pk,
        action="contractor.payment.created",
    ))
    approved = list(AuditEvent.objects.filter(
        entity_id=record.pk,
        action="contractor.payment.approved",
    ))

    if len(created) != 1 or len(approved) != 1:
        return None

    creation, approval = created[0], approved[0]

    if type(creation.payload) is not dict:
        return None
    if type(approval.payload) is not dict:
        return None
    if creation.actor_id != record.created_by_id:
        return None
    if approval.actor_id != record.approved_by_id:
        return None
    if approval.sequence <= creation.sequence:
        return None
    if creation.payload.get("engagement_id") != str(record.engagement_id):
        return None
    if creation.payload.get("kind") != record.kind:
        return None
    if creation.payload.get("amount") != str(record.final_amount):
        return None
    if approval.payload.get("amount") != str(record.final_amount):
        return None

    candidate = candidate_audited_technical_period(
        subject_id=user_id,
        project_id=record.project_id,
        earned_on=earned_on,
    )

    return Role.TECHNICIAN if candidate == Role.TECHNICIAN else None


def technical_payment_link_grants_live_access(*args, **kwargs):
    """A candidate match never grants manager payroll visibility."""
    return False