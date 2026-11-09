"""Unregistered, read-only MSR equipment-to-physical-unit mapping.

Each approved equipment row with quantity N expands to N independent
unit identifiers. No catalog lookup, record creation, serial assertion,
exception approval, or installation authorization occurs here.
"""
from dataclasses import dataclass
from uuid import UUID

from .equipment_invoice_rows import (
    MAX_INVOICE_ROWS,
    NEW_MSR_FIELDS,
    project_equipment_rows,
)


@dataclass(frozen=True)
class PhysicalUnit:
    msr_id: str
    unit_id: str
    row_number: int
    unit_number: int
    brand: str
    residential_system_type: str
    model_number: str
    description: str
    category_of_work: str


def physical_units_from_snapshot(*, msr_id, snapshot):
    """Return a detached tuple. Unsupported legacy rows fail closed."""
    try:
        validated_msr = str(UUID(str(msr_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A valid approved MSR identifier is required.") from None

    if type(snapshot) is not dict:
        raise ValueError("An approved MSR snapshot is required.")

    equipment = snapshot.get("equipment")
    if type(equipment) is not list or not equipment:
        raise ValueError("An explicit equipment list is required.")
    if len(equipment) > MAX_INVOICE_ROWS:
        raise ValueError("More than eight equipment rows are not supported.")

    # Reuse the existing customer-facing row validation, but do not
    # make or change an Invoice.
    project_equipment_rows(snapshot)

    result = []
    for row_number, source in enumerate(equipment, start=1):
        if type(source) is not dict or set(source) != NEW_MSR_FIELDS:
            raise ValueError(
                f"Equipment row {row_number} is not a complete catalog snapshot."
            )

        quantity = source["quantity"]
        for unit_number in range(1, quantity + 1):
            result.append(PhysicalUnit(
                msr_id=validated_msr,
                unit_id=f"ROW-{row_number:03d}-UNIT-{unit_number:03d}",
                row_number=row_number,
                unit_number=unit_number,
                brand=source["brand"],
                residential_system_type=source["residential_system_type"],
                model_number=source["model_number"],
                description=source["description"],
                category_of_work=source["category_of_work"],
            ))

    return tuple(result)