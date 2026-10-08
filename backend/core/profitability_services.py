"""GECC project profitability calculation services."""

from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

from .models import Project, ProjectCostRecord


COST_FIELDS = (
    'equipment_cost',
    'material_cost',
    'dealer_fee',
    'lead_cost',
    'technician_cost',
    'damon_cost',
    'jerry_cost',
)


def calculate_gross_profit(project_id):
    """Calculate Gross Profit from approved MSR and approved costs."""

    project = (
        Project.objects
        .select_related('current_approved')
        .get(pk=project_id)
    )

    msr = project.current_approved

    if msr is None or msr.status != 'APPROVED':
        raise ValidationError(
            'Project must have a current approved MSR.'
        )

    cost_record = (
        ProjectCostRecord.objects
        .filter(
            project=project,
            msr=msr,
            status=ProjectCostRecord.Status.APPROVED,
        )
        .order_by('-version')
        .first()
    )

    if cost_record is None:
        raise ValidationError(
            'Project must have an approved cost record.'
        )

    try:
        invoice_amount = Decimal(
            str(msr.snapshot['total_price'])
        )
    except (KeyError, TypeError, InvalidOperation):
        raise ValidationError(
            'Approved MSR must contain a valid invoice amount.'
        )

    total_cost = sum(
        (
            Decimal(str(getattr(cost_record, field)))
            for field in COST_FIELDS
        ),
        Decimal('0.00'),
    )

    gross_profit = invoice_amount - total_cost

    return {
        'project_id': str(project.id),
        'msr_id': str(msr.id),
        'cost_record_id': str(cost_record.id),
        'invoice_amount': invoice_amount,
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'cost_snapshot': {
            field: str(getattr(cost_record, field))
            for field in COST_FIELDS
        },
    }
