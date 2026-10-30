"""Read-only completed-installation detail for monthly financial audit.

Installation completion does not establish authenticated completion signing.
Financial statement reconciliation is intentionally handled separately.
"""

from decimal import Decimal

from rest_framework.exceptions import PermissionDenied

from .financial_reporting_calendar import get_corporate_reporting_period
from .models import (
    InstallationSchedule,
    ProjectCostRecord,
    Role,
    User,
)
from .project_cost_services import COST_FIELDS


def get_monthly_completed_project_audit(actor, year, month):
    """Return project completion and cost evidence for a calendar month."""

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied(
            "Only an active Comptroller may review monthly financial audit detail."
        )

    if not User.objects.filter(
        pk=actor.pk,
        is_active=True,
        role=Role.COMPTROLLER,
    ).exists():
        raise PermissionDenied(
            "An active Comptroller account is required."
        )

    period = get_corporate_reporting_period("MONTHLY", year, month)

    schedules = (
        InstallationSchedule.objects
        .filter(
            status=InstallationSchedule.Status.COMPLETED,
            completed_at__date__gte=period.start_date,
            completed_at__date__lte=period.end_date,
        )
        .select_related("project", "project__customer")
        .order_by("completed_at", "pk")
    )

    projects = []
    seen_project_ids = set()

    for schedule in schedules:
        project = schedule.project

        if project.pk in seen_project_ids:
            continue

        seen_project_ids.add(project.pk)

        approved_costs = (
            ProjectCostRecord.objects
            .filter(
                project=project,
                status=ProjectCostRecord.Status.APPROVED,
            )
            .order_by("-version", "-approved_at", "-pk")
        )

        cost_record = approved_costs.first()

        categories = {
            field: str(getattr(cost_record, field))
            if cost_record is not None else None
            for field in COST_FIELDS
        }

        total = (
            sum(
                (Decimal(str(getattr(cost_record, field))) for field in COST_FIELDS),
                Decimal("0.00"),
            )
            if cost_record is not None else None
        )

        projects.append({
            "project_id": str(project.pk),
            "project_code": project.code,
            "customer_id": str(project.customer_id),
            "installation_schedule_id": str(schedule.pk),
            "installation_completed_at": schedule.completed_at.isoformat(),
            "installation_status": "COMPLETED",
            "completion_certificate_status": "NOT_VERIFIED",
            "cost_record_id": str(cost_record.pk) if cost_record else None,
            "cost_record_version": cost_record.version if cost_record else None,
            "approved_cost_record_count": approved_costs.count(),
            "cost_categories": categories,
            "cost_total": str(total) if total is not None else None,
            "cost_reconciliation_status": "NOT_YET_VERIFIED",
        })

    return {
        "frequency": "MONTHLY",
        "year": period.year,
        "month": period.period_number,
        "period_start": period.start_date.isoformat(),
        "period_end": period.end_date.isoformat(),
        "completion_basis": "INSTALLATION_COMPLETED_AT",
        "certificate_verification_basis": "NOT_YET_AUTHENTICATED",
        "completed_project_count": len(projects),
        "projects": projects,
    }
