"""MSR-approved snapshot is the source for all shared document values.

No database access, routes, or document writes are performed here.
Installation-stage evidence is handled by separately authorized records.
"""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .equipment_catalog_snapshot import customer_equipment_description


COMMON_MSR_FIELDS = (
    "customer",
    "billing_address",
    "project_location",
    "project_city",
    "project_state",
    "project_zip",
    "customer_phone",
    "customer_email",
)


def customer_document_data(snapshot):
    """Return an independent copy of approved customer/project values."""
    if type(snapshot) is not dict:
        raise ValueError("MSR snapshot must be an object.")

    values = {}
    for key in COMMON_MSR_FIELDS:
        value = snapshot.get(key, "")
        if type(value) is not str:
            raise ValueError(f"MSR field {key} must be text.")
        values[key] = value

    equipment = snapshot.get("equipment", [])
    if type(equipment) is not list:
        raise ValueError("MSR equipment must be a list.")

    copied = deepcopy(equipment)
    for item in copied:
        if type(item) is not dict:
            raise ValueError("Equipment lines must be objects.")
        customer_equipment_description(item)

    values["equipment"] = copied
    return values


def document_customer_name(snapshot):
    """Every document uses exactly the same MSR customer name."""
    name = customer_document_data(snapshot)["customer"]
    if not name.strip():
        raise ValueError("Customer name is required.")
    return name


def msr_other_details(snapshot):
    """Read approved promotion/discount values without mutating MSR."""
    if type(snapshot) is not dict:
        raise ValueError("MSR snapshot must be an object.")

    other = snapshot.get("other")
    if other is None:
        return None
    if type(other) is not dict:
        raise ValueError("MSR Other must be an object.")

    category = other.get("type")
    explanation = other.get("notes")
    amount = other.get("amount")

    if type(category) is not str or not category.strip():
        raise ValueError("MSR Other type is required.")
    if type(explanation) is not str or not explanation.strip():
        raise ValueError("MSR Other explanation is required.")
    if type(amount) not in (str, int, float, Decimal):
        raise ValueError("MSR Other amount is invalid.")

    try:
        number = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise ValueError("MSR Other amount must be numeric.")

    if not number.is_finite() or number < 0:
        raise ValueError("MSR Other amount must be nonnegative.")

    return {
        "type": category.strip(),
        "notes": explanation.strip(),
        "amount": str(number.quantize(Decimal("0.01"))),
    }


def invoice_other_display(snapshot):
    """Display only an approved, price-reducing Other as negative.

    Cash back and free equipment cannot automatically reduce an invoice.
    """
    other = msr_other_details(snapshot)
    if other is None:
        return None

    if other.get("type") not in ("Reduced Price", "Marketing Promotion"):
        return None

    number = Decimal(other["amount"])
    return f"-{number:.2f}"


def invoice_other_notes(snapshot):
    other = msr_other_details(snapshot)
    if other is None:
        return ""
    return f'{other["type"]}: {other["notes"]}'