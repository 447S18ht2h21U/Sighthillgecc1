"""Verify new named-catalog selections at the MSR edit boundary.

Historical persisted equipment remains a value snapshot and is not
revalidated against mutable catalog activation or description status.
"""
import copy
from collections import Counter
from uuid import UUID

from rest_framework.exceptions import ValidationError

from .models import ProductCatalogMembership


IDENTITY_FIELDS = (
    "brand", "residential_system_type",
    "model_number", "description",
)
REFERENCE_FIELDS = frozenset(("catalog_id", "equipment_id"))


def identity(line):
    if type(line) is not dict:
        return None
    if not all(name in line for name in IDENTITY_FIELDS):
        return None
    return tuple(line[name] for name in IDENTITY_FIELDS)


def verify_new_equipment_selections(proposed, persisted):
    """Require active membership for newly introduced six-field lines.

    The caller must invoke this only for edits of the active draft,
    inside the existing MSR transaction. Do not call during submission
    or on approved historical versions.
    """
    if type(proposed) is not dict:
        return proposed

    checked = copy.deepcopy(proposed)
    incoming = checked.get("equipment")
    if type(incoming) is not list:
        return checked

    previous = (
        persisted.get("equipment", [])
        if type(persisted) is dict else []
    )
    if type(previous) is not list:
        previous = []

    previous_counts = Counter(
        key for row in previous
        if (key := identity(row)) is not None
    )

    for line in incoming:
        if type(line) is not dict:
            continue

        key = identity(line)
        references = REFERENCE_FIELDS.intersection(line)

        # Existing, identical catalog equipment retains its historical
        # values even when the source catalog is later deactivated.
        if key is not None and previous_counts[key] > 0 and not references:
            previous_counts[key] -= 1
            continue

        if key is None and not references:
            # Existing legacy validation remains independently enforced.
            continue

        if references != REFERENCE_FIELDS:
            raise ValidationError({
                "equipment": "New catalog equipment requires both catalog and product IDs."
            })

        if key is None:
            raise ValidationError({
                "equipment": "Catalog equipment details are incomplete."
            })

        try:
            catalog_id = UUID(str(line["catalog_id"]))
            equipment_id = UUID(str(line["equipment_id"]))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({
                "equipment": "Invalid catalog or equipment identifier."
            })

        membership = (
            ProductCatalogMembership.objects
            .select_related("catalog", "equipment")
            .filter(
                catalog_id=catalog_id,
                equipment_id=equipment_id,
                catalog__is_active=True,
                equipment__is_active=True,
            )
            .first()
        )

        if membership is None:
            raise ValidationError({
                "equipment": "Selected product is not active in the selected catalog."
            })

        equipment = membership.equipment

        if any(
            line[field] != getattr(equipment, field)
            for field in IDENTITY_FIELDS
        ):
            raise ValidationError({
                "equipment": "Equipment details do not match the verified catalog revision."
            })

        # IDs are proof of selection, not part of the six-field
        # historical customer-facing equipment snapshot.
        line.pop("catalog_id")
        line.pop("equipment_id")

    return checked
