from datetime import timedelta
from zoneinfo import ZoneInfo
EASTERN = ZoneInfo('America/New_York')
PAYMENT_OPTIONS = ('50_PERCENT_DEPOSIT', '100_PERCENT_COMPLETION')
def installation_eligible_at(customer_contract_signed_at, customer_invoice_signed_at, rescission_deadline):
    """Earliest gate only: scheduling also requires signatures and verified required deposit."""
    if not all((customer_contract_signed_at, customer_invoice_signed_at, rescission_deadline)):
        return None
    if any(x.tzinfo is None or x.utcoffset() is None for x in (customer_contract_signed_at, customer_invoice_signed_at, rescission_deadline)):
        raise ValueError('Timezone-aware timestamps required.')
    latest = max(customer_contract_signed_at, customer_invoice_signed_at).astimezone(EASTERN)
    five_calendar_days = latest + timedelta(days=5)
    return max(five_calendar_days, rescission_deadline.astimezone(EASTERN))
SIGNATURE_WORKFLOWS = {
    'contract': ['customer_signature', 'gecc_signature'],
    'invoice': ['customer_signature', 'gecc_signature'],
    'completion_financed': ['gecc_signature', 'customer_signature'],
    'completion_non_financed': ['gecc_signature', 'customer_signature'],
}
