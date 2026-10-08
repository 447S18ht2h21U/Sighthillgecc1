"""GECC project cost record approval services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .contractor_services import require_comptroller
from .models import ProjectCostRecord
from .services import audit


COST_FIELDS = (
    'equipment_cost',
    'material_cost',
    'dealer_fee',
    'technician_cost',
    'lead_cost',
    'damon_cost',
    'jerry_cost',
)


@transaction.atomic
def approve_project_cost_record(actor, record_id):
    """Approve validated project costs through the Comptroller."""

    require_comptroller(actor)

    record = (
        ProjectCostRecord.objects
        .select_for_update()
        .select_related('msr', 'project')
        .get(pk=record_id)
    )

    if record.status != ProjectCostRecord.Status.DRAFT:
        raise ValidationError(
            'Only draft project cost records may be approved.'
        )

    if (
        record.msr.project_id != record.project_id
        or record.msr.status != 'APPROVED'
        or record.project.current_approved_id != record.msr_id
    ):
        raise ValidationError(
            'Costs must reference the current approved MSR '
            'for the same project.'
        )

    for field in COST_FIELDS:
        amount = getattr(record, field)
        if amount is None or not Decimal(str(amount)).is_finite():
            raise ValidationError(
                f'{field} must be a finite monetary amount.'
            )
        if amount < 0:
            raise ValidationError(
                f'{field} cannot be negative.'
            )

    record.status = ProjectCostRecord.Status.APPROVED
    record.approved_by = actor
    record.approved_at = timezone.now()

    record.save(
        update_fields=['status', 'approved_by', 'approved_at']
    )

    audit(
        actor,
        'project.costs.approved',
        record.id,
        {
            'project_id': str(record.project_id),
            'msr_id': str(record.msr_id),
            'version': record.version,
            'costs': {
                field: str(getattr(record, field))
                for field in COST_FIELDS
            },
        },
    )

    return record
