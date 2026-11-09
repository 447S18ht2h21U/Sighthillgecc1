"""Proposed revised-invoice values derived only from an approved MSR snapshot.

Pure projection: does not generate PDFs, change approvals, or access databases.
Do not connect to the protected old PDF template: it lacks a Notes field.
"""

from decimal import Decimal, InvalidOperation

from .msr_document_source import (
    document_customer_name,
    msr_other_details,
    invoice_other_notes,
)


def _usd(snapshot, key):
    try:
        value = Decimal(str(snapshot[key]))
        if (
            not value.is_finite()
            or value < 0
            or value != value.quantize(Decimal("0.01"))
        ):
            raise ValueError()
        return value
    except (KeyError, InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid MSR money field: {key}")


def revised_invoice_projection(snapshot):
    """One and only one discount deduction in the Invoice Other row."""
    customer = document_customer_name(snapshot)
    base = _usd(snapshot, "base_price")
    discount = _usd(snapshot, "discount")
    tax = _usd(snapshot, "tax")
    total = _usd(snapshot, "total_price")

    if total <= 0 or base - discount + tax != total:
        raise ValueError("Invoice totals disagree with the MSR.")

    other = msr_other_details(snapshot)
    notes = invoice_other_notes(snapshot)

    if other is not None:
        amount = Decimal(other["amount"])
        kind = other["type"]

        if kind == "Reduced Price":
            if amount != discount:
                raise ValueError("Reduced Price must equal MSR discount.")

        elif kind == "Marketing Promotion":
            if discount not in (Decimal("0"), amount):
                raise ValueError("Promotion amount and discount disagree.")

        elif discount:
            # A cash-back or free-equipment benefit is not automatically
            # a reduction in the price owed. Avoid inventing its treatment.
            raise ValueError(
                "Non-price promotion cannot silently reduce the invoice."
            )

    elif discount:
        # Preserve a valid older MSR that predates the Other field.
        notes = "Approved MSR price reduction."

    return {
        "customer_name": customer,
        "subtotal": f"{base:,.2f}",
        "other_charges": f"-{discount:,.2f}" if discount else "0.00",
        "sales_tax": f"{tax:,.2f}",
        "invoice_total": f"{total:,.2f}",
        "notes": notes,
    }

def complete_invoice_projection(snapshot):
    """Proposed combined Invoice fields; no live PDF rendering or writes."""
    from .equipment_invoice_rows import invoice_equipment_field_values

    values = revised_invoice_projection(snapshot)
    equipment = invoice_equipment_field_values(snapshot)
    if set(values).intersection(equipment):
        raise ValueError("Invoice field collision.")
    return {**values, **equipment}
