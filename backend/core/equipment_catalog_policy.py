"""Shared residential equipment catalog rules.

No live API, migrations, or document writes are enabled here.
Approved project/document snapshots must not reference mutable catalog data.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .models import Role


FIELDS = (
    "brand",
    "residential_system_type",
    "model_number",
    "description",
)

FIELD_LIMITS = MappingProxyType({
    "brand": 120,
    "residential_system_type": 200,
    "model_number": 120,
    "description": 1000,
})

MANAGER_ROLES = frozenset({
    Role.SALES_MANAGER,
    Role.INSTALLATION_MANAGER,
})


@dataclass(frozen=True)
class EquipmentDetails:
    brand: str
    residential_system_type: str
    model_number: str
    description: str

    def snapshot(self):
        """Return independent primitive values for historical documents."""
        return {
            field: getattr(self, field)
            for field in FIELDS
        }


def manager_may_manage_equipment(actor):
    """Only active, authenticated permanent manager roles may edit."""
    return (
        actor is not None
        and getattr(actor, "is_authenticated", False)
        and getattr(actor, "is_active", False)
        and getattr(actor, "role", None) in MANAGER_ROLES
    )


def validate_equipment_details(values):
    """Require exactly four complete independently entered fields.

    Preserve model-family wildcards, case and punctuation. Normalize
    surrounding whitespace without silently inventing missing values.
    """
    if type(values) is not dict or set(values) != set(FIELDS):
        raise ValueError("Exactly four equipment fields are required.")

    normalized = {}
    for field in FIELDS:
        value = values[field]
        if type(value) is not str:
            raise ValueError(f"{field} must be text.")
        value = value.strip()
        if not value:
            raise ValueError(f"{field} is required.")
        if len(value) > FIELD_LIMITS[field]:
            raise ValueError(f"{field} exceeds its length limit.")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(f"{field} contains a control character.")
        normalized[field] = value

    return EquipmentDetails(**normalized)


def equipment_snapshot(details):
    """Never expose an editable catalog object as document evidence."""
    if type(details) is not EquipmentDetails:
        raise ValueError("Validated equipment details are required.")
    return details.snapshot()