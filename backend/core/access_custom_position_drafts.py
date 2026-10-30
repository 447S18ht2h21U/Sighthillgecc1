"""Non-executable validation of proposed VERIDIAN positions and permissions.

This module creates no users, roles, grants, approvals, or database records.
Existing backend authorization remains authoritative.
"""

import re
from dataclasses import dataclass

from .access_permission_catalog import PERMISSION_BY_CODE
from .access_position_templates import POSITION_TEMPLATES


@dataclass(frozen=True)
class PositionDraft:
    title: str
    description: str
    permission_codes: tuple[str, ...]
    requires_independent_approval: bool


def validate_position_draft(title, description, permission_codes):
    """Validate draft metadata; never authorize system access."""

    if not isinstance(title, str) or not isinstance(description, str):
        raise ValueError("Position title and description must be text.")

    title = title.strip()
    description = description.strip()

    if not 3 <= len(title) <= 100:
        raise ValueError("Position title must contain 3 to 100 characters.")

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 &()/.,'-]*", title):
        raise ValueError("Position title contains unsupported characters.")

    reserved = {
        name.casefold()
        for position in POSITION_TEMPLATES
        for name in (position.code, position.label)
    }

    if title.casefold() in reserved:
        raise ValueError("This position is already a protected standard role.")

    if not 10 <= len(description) <= 2000:
        raise ValueError("Position description must contain 10 to 2000 characters.")

    if not isinstance(permission_codes, (tuple, list)):
        raise ValueError("Permissions must be an explicit list.")

    if len(permission_codes) > len(PERMISSION_BY_CODE):
        raise ValueError("Too many permission selections.")

    if any(not isinstance(code, str) for code in permission_codes):
        raise ValueError("Permission codes must be text.")

    codes = tuple(permission_codes)

    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate permission selection.")

    if any(code not in PERMISSION_BY_CODE for code in codes):
        raise ValueError("Unknown permission selection.")

    return PositionDraft(
        title=title,
        description=description,
        permission_codes=codes,
        requires_independent_approval=any(
            PERMISSION_BY_CODE[code].independent_approval
            for code in codes
        ),
    )


def draft_grants_access(*args, **kwargs):
    """A proposed position or permission selection never grants access."""
    return False