"""Unregistered, read-only MSR equipment-to-physical-unit mapping.

Each approved equipment row with quantity N expands to N independent
unit identifiers. No catalog lookup, record creation, serial assertion,
exception approval, or installation authorization occurs here.
"""
from dataclasses import dataclass
from uuid import UUID

from .equipment_package_requirements_6029 import (
    expand_purchase_requirement,
)

from .equipment_invoice_rows import (
    MAX_MSR_EQUIPMENT_ROWS,
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
    """Return detached, package-aware physical equipment identities."""

    try:

        validated_msr = str(UUID(str(msr_id)))

    except (ValueError, TypeError, AttributeError):

        raise ValueError(
            "A valid approved MSR identifier is required."
        ) from None

    if type(snapshot) is not dict:

        raise ValueError(
            "An approved MSR snapshot is required."
        )

    equipment = snapshot.get("equipment")

    if type(equipment) is not list or not equipment:

        raise ValueError(
            "An explicit equipment list is required."
        )

    if len(equipment) > MAX_MSR_EQUIPMENT_ROWS:

        raise ValueError(
            "MSR equipment exceeds 100 entries."
        )

    project_equipment_rows(snapshot)

    result = []

    for row_number, source in enumerate(
        equipment,
        start=1,
    ):

        if (
            type(source) is not dict
            or set(source) != NEW_MSR_FIELDS
        ):

            raise ValueError(
                f"Equipment row {row_number} is not "
                "a complete catalog snapshot."
            )

        quantity = source["quantity"]

        components = expand_purchase_requirement(
            model_number=source["model_number"],
            quantity=1,
        )

        for unit_number in range(1, quantity + 1):

            for component_number, component in enumerate(
                components,
                start=1,
            ):

                if component["quantity"] != 1:

                    raise ValueError(
                        "Package component multiplicity "
                        "requires a separate inventory definition."
                    )

                unit_id = (
                    f"ROW-{row_number:03d}"
                    f"-UNIT-{unit_number:03d}"
                )

                is_package = len(components) > 1

                if is_package:

                    unit_id += (
                        f"-COMP-{component_number:03d}"
                    )

                result.append(PhysicalUnit(
                    msr_id=validated_msr,
                    unit_id=unit_id,
                    row_number=row_number,
                    unit_number=unit_number,
                    brand=source["brand"],
                    residential_system_type=(
                        source["residential_system_type"]
                    ),
                    model_number=component["model_number"],
                    description=(
                        "Component of approved equipment package"
                        if is_package
                        else source["description"]
                    ),
                    category_of_work=(
                        source["category_of_work"]
                    ),
                ))

                if len(result) > 10000:

                    raise ValueError(
                        "Physical equipment inventory "
                        "exceeds the review limit."
                    )

    identifiers = [
        unit.unit_id
        for unit in result
    ]

    if len(identifiers) != len(set(identifiers)):

        raise ValueError(
            "Physical equipment identities are duplicated."
        )

    return tuple(result)
