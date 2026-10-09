"""GECC biweekly commission report services."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    CommissionRecord,
    CommissionReport,
)
from .services import (
    audit,
    authorize,
)


@transaction.atomic
def create_commission_report(
    actor,
    period_start,
    period_end,
):
    """
    Create a draft biweekly commission report
    from approved commission records.
    """

    if period_end < period_start:
        raise ValidationError(
            'Report end date cannot be before start date.'
        )

    existing = CommissionReport.objects.filter(
        period_start=period_start,
        period_end=period_end,
    ).first()

    if existing:
        raise ValidationError(
            'A commission report already exists for this period.'
        )

    records = (
        CommissionRecord.objects
        .filter(
            status=CommissionRecord.Status.APPROVED,
            approved_at__date__gte=period_start,
            approved_at__date__lte=period_end,
        )
        .select_related(
            'project',
            'recipient',
        )
    )

    snapshot_records = []

    for record in records:
        snapshot_records.append(
            {
                'commission_record_id': str(
                    record.id
                ),
                'project_id': str(
                    record.project_id
                ),
                'recipient_id': str(
                    record.recipient_id
                ),
                'kind': record.kind,
                'amount': str(
                    record.final_amount
                ),
                'calculation_snapshot': record.calculation_snapshot,
            }
        )

    report = CommissionReport.objects.create(
        period_start=period_start,
        period_end=period_end,
        report_snapshot={
            'records': snapshot_records,
            'record_count': len(snapshot_records),
        },
        created_by=actor,
    )

    audit(
        actor,
        'commission.report.created',
        report.id,
        {
            'period_start': str(period_start),
            'period_end': str(period_end),
            'record_count': len(snapshot_records),
        },
    )

    return report


@transaction.atomic
def approve_commission_report(
    actor,
    report_id,
):
    """
    Approve a draft commission report.
    """

    report = (
        CommissionReport.objects
        .select_for_update()
        .get(pk=report_id)
    )

    if report.status != CommissionReport.Status.DRAFT:
        raise ValidationError(
            'Only draft commission reports may be approved.'
        )

    report.status = CommissionReport.Status.APPROVED
    report.approved_by = actor
    report.approved_at = timezone.now()

    report.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_at',
        ]
    )

    audit(
        actor,
        'commission.report.approved',
        report.id,
        {
            'period_start': str(report.period_start),
            'period_end': str(report.period_end),
        },
    )

    return report