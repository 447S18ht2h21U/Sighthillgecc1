"""GECC commission record creation and approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .commission_eligibility_services import (
    get_commission_eligibility,
)
from .commission_services import (
    calculate_commissions,
)
from .models import (
    CommissionRecord,
    Project,
)

from .services import (
    audit,
    authorize,
)


@transaction.atomic
def create_commission_records(actor, project_id):
    """
    Create draft commission records from an eligible project.
    """

    eligibility = get_commission_eligibility(
        project_id
    )

    if not eligibility['eligible']:
        raise ValidationError(
            eligibility['reason']
        )

    calculation = calculate_commissions(
        project_id
    )

    project = Project.objects.get(
    pk=project_id
    )

    records = []

    commissions = [
        (
            CommissionRecord.Kind.RYAN_VARIABLE,
            Decimal('0.15'),
            calculation['ryan_commission'],
        ),
        (
            CommissionRecord.Kind.DOUG_VARIABLE,
            Decimal('0.05'),
            calculation['doug_commission'],
        ),
    ]

    for kind, rate, amount in commissions:

        record, created = CommissionRecord.objects.get_or_create(
            project=project,
            msr_id=calculation['msr_id'],
            kind=kind,
            defaults={
                'recipient': project.sales_associate,
                'rate': rate,
                'basis_amount': calculation['gross_profit'],
                'deduction_amount': Decimal('0.00'),
                'final_amount': amount,
                'calculation_snapshot': calculation[
                    'calculation_snapshot'
                ],
                'created_by': actor,
            },
        )

        if created:
            audit(
                actor,
                'commission.record.created',
                record.id,
                {
                    'project_id': str(project.id),
                    'kind': kind,
                    'amount': str(amount),
                },
            )

        records.append(record)

    return records


@transaction.atomic
def approve_commission_record(actor, record_id):
    """
    Approve a draft commission record.
    """

    record = (
        CommissionRecord.objects
        .select_for_update()
        .select_related('project')
        .get(pk=record_id)
    )

    authorize(
        actor,
        record.project,
        approval=True,
    )

    if record.status != CommissionRecord.Status.DRAFT:
        raise ValidationError(
            'Only draft commission records may be approved.'
        )

    record.status = CommissionRecord.Status.APPROVED
    record.approved_by = actor
    record.approved_at = timezone.now()

    record.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_at',
        ]
    )

    audit(
        actor,
        'commission.record.approved',
        record.id,
        {
            'project_id': str(record.project_id),
            'kind': record.kind,
            'amount': str(record.final_amount),
        },
    )

    return record
