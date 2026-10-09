"""GECC corporate financial reporting services."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    FinancialReport,
    MSR,
    ProjectCostRecord,
    ContractorPaymentRecord,
    EmployeePayrollRecord,
    CommissionRecord,
    CustomerPayment,
)
from .services import audit

@transaction.atomic
def create_income_statement(
    actor,
    period_start,
    period_end,
):
    """
    Create a draft income statement snapshot.
    """

    existing = FinancialReport.objects.filter(
        kind=FinancialReport.Kind.INCOME_STATEMENT,
        period_start=period_start,
        period_end=period_end,
    ).first()

    if existing:
        raise ValidationError(
            'An income statement already exists for this period.'
        )

    approved_msrs = MSR.objects.filter(
        status='APPROVED',
        approved_at__date__gte=period_start,
        approved_at__date__lte=period_end,
    )

    revenue = sum(
        (
            Decimal(
                str(msr.snapshot.get('total_price', '0'))
            )
            for msr in approved_msrs
        ),
        Decimal('0.00'),
    )

    project_costs = ProjectCostRecord.objects.filter(
        status='APPROVED',
        approved_at__date__gte=period_start,
        approved_at__date__lte=period_end,
    )

    direct_costs = sum(
    (
        record.equipment_cost
        + record.material_cost
        + record.dealer_fee
        + record.technician_cost
        + record.lead_cost
        + record.damon_cost
        + record.jerry_cost
        for record in project_costs
    ),
    Decimal('0.00'),
)

    contractor_expense = sum(
        (
            record.final_amount
            for record in ContractorPaymentRecord.objects.filter(
                status=ContractorPaymentRecord.Status.PAID,
                paid_at__date__gte=period_start,
                paid_at__date__lte=period_end,
            )
        ),
        Decimal('0.00'),
    )

    employee_expense = sum(
        (
            record.net_amount
            for record in EmployeePayrollRecord.objects.filter(
                status=EmployeePayrollRecord.Status.PAID,
                paid_at__date__gte=period_start,
                paid_at__date__lte=period_end,
            )
        ),
        Decimal('0.00'),
    )

    commission_expense = sum(
        (
            record.final_amount
            for record in CommissionRecord.objects.filter(
                status=CommissionRecord.Status.APPROVED,
                approved_at__date__gte=period_start,
                approved_at__date__lte=period_end,
            )
        ),
        Decimal('0.00'),
    )

    gross_profit = revenue - direct_costs

    net_income = (
        gross_profit
        - contractor_expense
        - employee_expense
        - commission_expense
    )

    snapshot = {
        'revenue': str(revenue),
        'direct_costs': str(direct_costs),
        'gross_profit': str(gross_profit),
        'contractor_expense': str(contractor_expense),
        'employee_expense': str(employee_expense),
        'commission_expense': str(commission_expense),
        'net_income': str(net_income),
    }

    report = FinancialReport.objects.create(
        kind=FinancialReport.Kind.INCOME_STATEMENT,
        period_start=period_start,
        period_end=period_end,
        report_snapshot=snapshot,
        created_by=actor,
    )

    audit(
        actor,
        'financial_report.income_statement.created',
        report.id,
        snapshot,
    )

    return report


@transaction.atomic
def approve_financial_report(
    actor,
    report_id,
):
    """
    Approve a draft financial report.
    """

    report = (
        FinancialReport.objects
        .select_for_update()
        .get(pk=report_id)
    )

    if report.status != FinancialReport.Status.DRAFT:
        raise ValidationError(
            'Only draft financial reports may be approved.'
        )

    report.status = FinancialReport.Status.APPROVED
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
        'financial_report.approved',
        report.id,
        {
            'kind': report.kind,
            'period_start': str(report.period_start),
            'period_end': str(report.period_end),
        },
    )

    return report

@transaction.atomic
def create_balance_sheet(
    actor,
    period_end,
):
    """
    Create a draft balance sheet snapshot.
    """

    existing = FinancialReport.objects.filter(
        kind=FinancialReport.Kind.BALANCE_SHEET,
        period_start=period_end,
        period_end=period_end,
    ).first()

    if existing:
        raise ValidationError(
            'A balance sheet already exists for this period.'
        )

    verified_payments = CustomerPayment.objects.filter(
        status=CustomerPayment.Status.VERIFIED,
        received_date__lte=period_end,
    )

    cash = sum(
        (
            payment.amount
            for payment in verified_payments
        ),
        Decimal('0.00'),
    )

    contractor_liabilities = sum(
        (
            record.final_amount
            for record in ContractorPaymentRecord.objects.filter(
                status=ContractorPaymentRecord.Status.APPROVED,
            )
        ),
        Decimal('0.00'),
    )

    employee_liabilities = sum(
        (
            record.net_amount
            for record in EmployeePayrollRecord.objects.filter(
                status=EmployeePayrollRecord.Status.APPROVED,
            )
        ),
        Decimal('0.00'),
    )

    snapshot = {
        'cash': str(cash),
        'contractor_liabilities': str(
            contractor_liabilities
        ),
        'employee_payroll_liabilities': str(
            employee_liabilities
        ),
        'total_assets': str(cash),
        'total_liabilities': str(
            contractor_liabilities
            + employee_liabilities
        ),
    }

    report = FinancialReport.objects.create(
        kind=FinancialReport.Kind.BALANCE_SHEET,
        period_start=period_end,
        period_end=period_end,
        report_snapshot=snapshot,
        created_by=actor,
    )

    audit(
        actor,
        'financial_report.balance_sheet.created',
        report.id,
        snapshot,
    )

    return report