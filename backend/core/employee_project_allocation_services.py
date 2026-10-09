from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import EmployeeProjectAllocation
from .services import audit


@transaction.atomic
def approve_employee_project_allocation(
    actor,
    allocation_id,
):
    allocation = (
        EmployeeProjectAllocation.objects
        .select_for_update()
        .get(pk=allocation_id)
    )

    if allocation.status != EmployeeProjectAllocation.Status.DRAFT:
        raise ValidationError(
            'Only draft allocations may be approved.'
        )

    if allocation.allocation_percentage <= 0:
        raise ValidationError(
            'Allocation percentage must be greater than zero.'
        )

    allocation.status = (
        EmployeeProjectAllocation.Status.APPROVED
    )

    allocation.approved_by = actor
    allocation.approved_at = timezone.now()

    allocation.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_at',
        ]
    )

    audit(
        actor,
        'employee_project_allocation.approved',
        allocation.id,
        {
            'employee_id': str(
                allocation.employee_id
            ),
            'project_id': str(
                allocation.project_id
            ),
            'allocation_percentage': str(
                allocation.allocation_percentage
            ),
        },
    )

    return allocation