"""Proposed MSR equipment-to-Invoice mapping; no live routes or writes.

New equipment entries require their own work category. Legacy records
remain unchanged and must not be assigned an invented category.
"""
from copy import deepcopy

MAX_INVOICE_ROWS = 8

WORK_CATEGORIES = frozenset({
    "New installation",
    "Replacing existing equipment",
    "Service & maintenance",
})

CATALOG_FIELDS = (
    "brand",
    "residential_system_type",
    "model_number",
    "description",
)

NEW_MSR_FIELDS = frozenset({
    *CATALOG_FIELDS,
    "quantity",
    "category_of_work",
})


def project_equipment_rows(snapshot):
    """Return exactly eight independent Invoice row dictionaries.

    These are proposed customer-facing values only. Identification,
    serial numbers and per-unit prices require separately controlled
    evidence and cannot be inferred from a project total.
    """
    if type(snapshot) is not dict:
        raise ValueError("An approved MSR snapshot object is required.")

    equipment = snapshot.get("equipment")
    if type(equipment) is not list:
        raise ValueError("MSR equipment must be a list.")
    if len(equipment) > MAX_INVOICE_ROWS:
        raise ValueError("The revised Invoice supports up to eight equipment rows.")

    rows = []
    for index, source in enumerate(equipment, 1):
        if type(source) is not dict:
            raise ValueError(f"Equipment row {index} must be an object.")

        if set(source) != NEW_MSR_FIELDS:
            raise ValueError(
                f"Equipment row {index} must have the four catalog fields, "
                "quantity and its own Category of Work."
            )

        category = source["category_of_work"]
        if type(category) is not str or category not in WORK_CATEGORIES:
            raise ValueError(f"Invalid Category of Work in equipment row {index}.")

        for key in CATALOG_FIELDS:
            value = source[key]
            if type(value) is not str or not value.strip():
                raise ValueError(f"Equipment row {index} requires {key}.")
            if value != value.strip():
                raise ValueError(
                    f"Equipment row {index} contains unnormalized {key}."
                )

        quantity = source["quantity"]
        if type(quantity) is not int or not 1 <= quantity <= 999:
            raise ValueError(f"Invalid quantity in equipment row {index}.")

        rows.append({
            "category": category,
            "brand": source["brand"],
            "system_type": source["residential_system_type"],
            "model_number": source["model_number"],
            "model_identification": "",
            "serial_number": "",
            "price": "",
        })

    while len(rows) < MAX_INVOICE_ROWS:
        rows.append({
            "category": "",
            "brand": "",
            "system_type": "",
            "model_number": "",
            "model_identification": "",
            "serial_number": "",
            "price": "",
        })

    return deepcopy(rows)


def invoice_equipment_field_values(snapshot):
    """Match the 8 x 7 interactive Invoice field naming convention."""
    result = {}
    for number, row in enumerate(project_equipment_rows(snapshot), 1):
        for field, value in row.items():
            result[f"line_{number}_{field}"] = value
    return result