from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .profitability_services import calculate_gross_profit


RYAN_RATE = Decimal('0.15')
DOUG_RATE = Decimal('0.05')


def calculate_commissions(project_id):
    """
    Calculate GECC project commissions from approved profitability data.

    Commission payment eligibility checks will be added separately.
    This function calculates only.
    """

    profitability = calculate_gross_profit(project_id)

    gross_profit = profitability['gross_profit']

    if gross_profit <= Decimal('0.00'):
        ryan_commission = Decimal('0.00')
        doug_commission = Decimal('0.00')
    else:
        ryan_commission = (
            gross_profit * RYAN_RATE
        ).quantize(Decimal('0.01'))

        doug_commission = (
            gross_profit * DOUG_RATE
        ).quantize(Decimal('0.01'))

    net_profit = (
        gross_profit
        - ryan_commission
        - doug_commission
    ).quantize(Decimal('0.01'))

    if net_profit <= Decimal('0.00'):
        ryan_commission = Decimal('0.00')
        doug_commission = Decimal('0.00')
        net_profit = gross_profit.quantize(
            Decimal('0.01')
        )

    return {
        'project_id': profitability['project_id'],
        'msr_id': profitability['msr_id'],
        'cost_record_id': profitability['cost_record_id'],
        'gross_profit': gross_profit,
        'ryan_commission': ryan_commission,
        'doug_commission': doug_commission,
        'net_profit': net_profit,
        'calculation_snapshot': {
            'invoice_amount': str(
                profitability['invoice_amount']
            ),
            'total_cost': str(
                profitability['total_cost']
            ),
            'gross_profit': str(
                gross_profit
            ),
            'ryan_rate': str(
                RYAN_RATE
            ),
            'doug_rate': str(
                DOUG_RATE
            ),
        },
    }