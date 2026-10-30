"""Proposed position templates for VERIDIAN.

Planning metadata only. Templates do not assign, grant, or enforce
permissions. Existing backend authorization remains authoritative.
"""

from dataclasses import dataclass

from .access_permission_catalog import PERMISSION_BY_CODE


@dataclass(frozen=True)
class PositionTemplate:
    code: str
    label: str
    proposed_permissions: tuple[str, ...] = ()


POSITION_TEMPLATES = (
    PositionTemplate("CEO", "Chief Executive Officer"),
    PositionTemplate("MARKETING", "Marketing"),
    PositionTemplate("SALES_ASSOCIATE", "Sales Associate"),
    PositionTemplate("SALES_MANAGER", "Sales Manager"),
    PositionTemplate("COMPTROLLER", "Comptroller"),
    PositionTemplate("INSTALLATION_MANAGER", "Installation Manager"),
    PositionTemplate("TECHNICIAN", "Technician"),
    PositionTemplate(
        "ACCOUNTS_PAYABLE_ASSOCIATE",
        "Accounts Payable Associate",
    ),
    PositionTemplate(
        "DATABASE_ADMINISTRATOR",
        "Database Administrator",
    ),
)

POSITION_BY_CODE = {
    template.code: template
    for template in POSITION_TEMPLATES
}

if len(POSITION_BY_CODE) != len(POSITION_TEMPLATES):
    raise RuntimeError("Duplicate VERIDIAN position codes.")

for template in POSITION_TEMPLATES:
    for code in template.proposed_permissions:
        if code not in PERMISSION_BY_CODE:
            raise RuntimeError(
                f"Unknown permission in position template: {code}"
            )


def describe_position(code):
    """Return proposed template metadata, not granted access."""
    return POSITION_BY_CODE.get(code)


def position_grants_permission(position_code, permission_code):
    """Fail closed: planning templates cannot grant access."""
    return False
