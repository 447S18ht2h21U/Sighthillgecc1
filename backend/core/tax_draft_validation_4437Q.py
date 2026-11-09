"""Unregistered tax draft validation. No posting, filing or persistence."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from rest_framework.exceptions import ValidationError
from .tax_entry_authorization_4437I import require_tax_entry_action

REQUIRED = ("tax_year", "accounting_period", "jurisdiction", "tax_category", "accounting_classification", "amount", "source_reference", "evidence_reference", "explanation", "filing_status")
EXTRA = ("tax_due_date", "project_related", "project_id", "approved_msr_id", "approved_msr_version", "billing_address", "installation_address", "delivery_address")
CLASSIFICATIONS = frozenset(("CURRENT_INCOME_TAX_EXPENSE", "DEFERRED_INCOME_TAX_EXPENSE", "OTHER_BUSINESS_TAX_EXPENSE", "TAX_PAYABLE", "TAX_PREPAYMENT_OR_RECEIVABLE", "ACTUAL_TAX_PAYMENT"))

def validate_tax_draft(actor, entry):
    current = require_tax_entry_action(actor, "PREPARE_DRAFT")
    if type(entry) is not dict or set(entry) - set(REQUIRED) - set(EXTRA):
        raise ValidationError("Invalid tax draft fields.")
    for field in REQUIRED:
        value = entry.get(field)
        if type(value) is not str or not value.strip() or len(value) > 2000:
            raise ValidationError("Missing or invalid draft field: " + field)
    if not re.fullmatch(r"[0-9]{4}", entry["tax_year"]):
        raise ValidationError("Invalid tax year.")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", entry["accounting_period"]):
        raise ValidationError("Invalid accounting period.")
    try:
        date.fromisoformat(entry["accounting_period"] + "-01")
    except ValueError as error:
        raise ValidationError("Invalid accounting month.") from error
    if entry["accounting_classification"] not in CLASSIFICATIONS:
        raise ValidationError("Unknown accounting classification.")
    try:
        amount = Decimal(entry["amount"])
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValidationError("Invalid amount.") from error
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValidationError("An evidence-backed positive amount with at most two decimals is required.")
    if entry["filing_status"] != "NOT_ESTABLISHED":
        raise ValidationError("Filing status cannot be asserted by an unverified draft.")
    delivery = entry.get("delivery_address")
    if delivery not in (None, ""):
        if (
            type(delivery) is not str
            or not delivery.strip()
            or len(delivery) > 2000
        ):
            raise ValidationError(
                "Delivery address must be meaningful text, at most 2000 characters."
            )
    due = entry.get("tax_due_date")
    if due not in (None, ""):
        if type(due) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", due):
            raise ValidationError("Invalid due-date format.")
        try:
            date.fromisoformat(due)
        except ValueError as error:
            raise ValidationError("Invalid due date.") from error
    related = entry.get("project_related", False)
    if type(related) is not bool:
        raise ValidationError("Project-related indicator must be explicit.")
    if related:
        for field in ("project_id", "approved_msr_id", "billing_address", "installation_address"):
            value = entry.get(field)
            if type(value) is not str or not value.strip():
                raise ValidationError("Missing approved project reference: " + field)
        version = entry.get("approved_msr_version")
        if type(version) is not int or version < 1:
            raise ValidationError("A positive approved MSR version is required.")
    result = deepcopy(entry)
    result["amount"] = format(amount, ".2f")
    result["prepared_by"] = str(current.pk)
    result["status"] = "DRAFT_VALIDATED_ONLY"
    result["eligible_for_financial_reporting"] = False
    return result
