"""Detached, customer-facing equipment snapshots for future MSR integration.

This is a pure adapter; no MSR, catalog, or document records are modified.
Only an approved draft workflow may later attach its output to an MSR.
"""

from .equipment_catalog_policy import (
    EquipmentDetails,
    equipment_snapshot,
    validate_equipment_details,
)


def snapshot_equipment_line(details, *, quantity):
    """Retain four catalog fields and quantity as independent JSON values."""
    if type(details) is not EquipmentDetails:
        raise ValueError("Validated catalog equipment is required.")
    if type(quantity) is not int or not 1 <= quantity <= 999:
        raise ValueError("Equipment quantity must be from 1 to 999.")
    return {**equipment_snapshot(details), "quantity": quantity}


def snapshot_catalog_item(item, *, quantity):
    """Read active catalog values, never a mutable database reference."""
    if item is None or getattr(item, "is_active", None) is not True:
        raise ValueError("An active catalog item is required.")
    values = {
        field: getattr(item, field)
        for field in (
            "brand", "residential_system_type",
            "model_number", "description",
        )
    }
    details = validate_equipment_details(values)
    return snapshot_equipment_line(details, quantity=quantity)


def customer_equipment_description(line):
    """Render all four fields without altering their underlying values."""
    if type(line) is not dict:
        raise ValueError("An equipment snapshot is required.")
    keys = (
        "brand", "residential_system_type",
        "model_number", "description",
    )
    if all(key not in line for key in keys[:3]):
        # Existing MSR equipment rows remain readable and unchanged.
        description = line.get("description")
        if type(description) is not str or not description.strip():
            raise ValueError("Existing equipment description is required.")
        return description

    details = validate_equipment_details({
        key: line.get(key) for key in keys
    })
    return (
        f"Brand: {details.brand} | "
        f"Residential system type: {details.residential_system_type} | "
        f"Model number: {details.model_number} | "
        f"Description: {details.description}"
    )