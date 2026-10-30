"""Non-executable validation of proposed permission scope.

This module grants no access and creates no project assignments.
"""

import uuid
from dataclasses import dataclass

from .access_permission_catalog import PERMISSION_BY_CODE


SCOPES = frozenset({
    "ASSIGNED_PROJECTS",
    "SPECIFIC_PROJECTS",
    "ALL_PROJECTS",
    "NOT_APPLICABLE",
})


@dataclass(frozen=True)
class PermissionScopeDraft:
    permission_code: str
    scope: str
    project_ids: tuple[uuid.UUID, ...]
    requires_independent_approval: bool


def validate_permission_scope_draft(permission_code, scope, project_ids=()):
    """Validate proposed scope only; never authorize access."""

    definition = PERMISSION_BY_CODE.get(permission_code)

    if definition is None:
        raise ValueError("Unknown permission.")

    if scope not in SCOPES:
        raise ValueError("Unknown permission scope.")

    if not isinstance(project_ids, (tuple, list)):
        raise ValueError("Project IDs must be an explicit list.")

    if len(project_ids) > 100:
        raise ValueError("Too many project IDs.")

    normalized = []

    for value in project_ids:
        if not isinstance(value, (uuid.UUID, str)):
            raise ValueError("Invalid project identifier.")

        try:
            normalized.append(uuid.UUID(str(value)))
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid project identifier.") from exc

    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate project identifier.")

    if definition.project_scoped:
        if scope == "NOT_APPLICABLE":
            raise ValueError("A project-scoped permission needs a scope.")

        if scope == "SPECIFIC_PROJECTS" and not normalized:
            raise ValueError("Specific project scope requires project IDs.")

        if scope != "SPECIFIC_PROJECTS" and normalized:
            raise ValueError("Project IDs are only allowed for specific projects.")
    else:
        if scope != "NOT_APPLICABLE" or normalized:
            raise ValueError("This permission does not use project scope.")

    return PermissionScopeDraft(
        permission_code=permission_code,
        scope=scope,
        project_ids=tuple(normalized),
        requires_independent_approval=(
            definition.independent_approval
            or (definition.project_scoped and scope == "ALL_PROJECTS")
        ),
    )


def scope_draft_grants_access(*args, **kwargs):
    """A scope proposal never creates operational authorization."""
    return False