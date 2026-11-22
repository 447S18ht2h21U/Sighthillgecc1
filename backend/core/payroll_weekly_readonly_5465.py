"""Read-only Comptroller payroll register; no payment authority."""
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .financial_reporting_authorization import require_financial_reporting_role
from .models import ContractorPaymentRecord, EmployeePayrollRecord, Role


def _iso(value):
    return value.isoformat() if value is not None else None


@never_cache
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weekly_payroll(request):
    require_financial_reporting_role(request.user, Role.COMPTROLLER)

    employee_records = (
        EmployeePayrollRecord.objects
        .select_related("employee")
        .order_by("-payroll_period_end", "-created_at")[:100]
    )
    contractor_records = (
        ContractorPaymentRecord.objects
        .select_related("engagement__contractor")
        .order_by("-payment_period_end", "-created_at")[:100]
    )

    rows = []
    for item in employee_records:
        rows.append({
            "id": str(item.pk),
            "type": "Employee",
            "person": item.employee.legal_name,
            "kind": item.get_kind_display(),
            "period_start": _iso(item.payroll_period_start),
            "period_end": _iso(item.payroll_period_end),
            "gross": str(item.gross_amount),
            "deductions": str(item.deduction_amount),
            "net": str(item.net_amount),
            "status": item.status,
            "approval_recorded_at": _iso(item.approved_at),
            "payment_recorded_at": _iso(item.paid_at),
            "settlement_independently_verified": False,
        })

    for item in contractor_records:
        rows.append({
            "id": str(item.pk),
            "type": "Contractor",
            "person": item.engagement.contractor.legal_name,
            "kind": item.get_kind_display(),
            "period_start": _iso(item.payment_period_start),
            "period_end": _iso(item.payment_period_end),
            "gross": str(item.basis_amount),
            "deductions": str(item.deduction_amount),
            "net": str(item.final_amount),
            "status": item.status,
            "approval_recorded_at": _iso(item.approved_at),
            "payment_recorded_at": _iso(item.paid_at),
            "settlement_independently_verified": False,
        })

    rows.sort(
        key=lambda row: (row["period_end"], row["id"]),
        reverse=True,
    )

    response = Response({
        "scope": "COMPTROLLER_COMPANY_WIDE",
        "read_only": True,
        "settlement_verification_included": False,
        "limited_to_latest": 100,
        "rows": rows[:100],
    })
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response