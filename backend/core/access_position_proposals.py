"""Nonbinding, proposed VERIDIAN position-access matrix.

Planning information only. These entries are not access grants.
The actual authorization services remain unchanged and authoritative.
"""

from .access_permission_catalog import PERMISSION_BY_CODE
from .access_position_templates import POSITION_BY_CODE


PROPOSED_ACCESS = {
    "CEO": (
        "dashboard.view",
        "compensation.own.view",
    ),
    "MARKETING": (
        "dashboard.view",
        "compensation.own.view",
    ),
    "SALES_ASSOCIATE": (
        "dashboard.view",
        "customers.view",
        "customers.manage",
        "compensation.own.view",
    ),
    "SALES_MANAGER": (
        "dashboard.view",
        "customers.view",
        "customers.manage",
        "compensation.own.view",
    ),
    "COMPTROLLER": (
        "dashboard.view",
        "customers.view",
        "customers.manage",
        "technician_assignments.view",
        "compensation.own.view",
    ),
    "INSTALLATION_MANAGER": (
        "dashboard.view",
        "technician_assignments.view",
        "compensation.own.view",
    ),
    "TECHNICIAN": (
        "dashboard.view",
        "compensation.own.view",
    ),
    "ACCOUNTS_PAYABLE_ASSOCIATE": (
        "dashboard.view",
        "compensation.own.view",
    ),
    "DATABASE_ADMINISTRATOR": (
        "dashboard.view",
        "compensation.own.view",
    ),
}


RESERVED_FOR_SEPARATE_APPROVAL = frozenset(
    item.code
    for item in PERMISSION_BY_CODE.values()
    if item.independent_approval
)


def proposed_permissions(position_code):
    """Describe a proposal only; never grant access."""
    return PROPOSED_ACCESS.get(position_code, ())


def proposed_access_granted(user, permission_code, *, project=None):
    """No proposal is executable authorization."""
    return False


if set(PROPOSED_ACCESS) != set(POSITION_BY_CODE):
    raise RuntimeError("Proposed positions do not match defined templates.")

for position_code, permissions in PROPOSED_ACCESS.items():
    if len(permissions) != len(set(permissions)):
        raise RuntimeError("Duplicate proposed permission.")
    for code in permissions:
        if code not in PERMISSION_BY_CODE:
            raise RuntimeError("Unknown proposed permission.")
        if code in RESERVED_FOR_SEPARATE_APPROVAL:
            raise RuntimeError("Independently approved right in default proposal.")

if "technician_assignments.create" in set().union(
    *(set(values) for values in PROPOSED_ACCESS.values())
):
    raise RuntimeError("Technician creation must not be auto-proposed.")

if "technician_assignments.end" in set().union(
    *(set(values) for values in PROPOSED_ACCESS.values())
):
    raise RuntimeError("Technician termination must not be auto-proposed.")
