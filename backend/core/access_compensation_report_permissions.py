"""Default-deny permission boundary for personal compensation reports.

This module grants no permissions and creates no API endpoints.

Position templates and proposed access matrices are never treated
as actual authorization grants.
"""

from rest_framework.exceptions import PermissionDenied

from .access_permission_catalog import (
    PERMISSION_BY_CODE,
    has_permission,
)
from .individual_compensation_report_with_evidence import (
    own_individual_compensation_report_with_evidence,
)


OWN_COMPENSATION_PERMISSION = "compensation.own.view"


def require_own_compensation_permission(actor):
    """Require an effective permission, not proposed position metadata."""

    definition = PERMISSION_BY_CODE.get(
        OWN_COMPENSATION_PERMISSION
    )

    if definition is None:
        raise PermissionDenied(
            "Individual compensation reporting is unavailable."
        )

    if not has_permission(actor, OWN_COMPENSATION_PERMISSION):
        raise PermissionDenied(
            "Individual compensation reporting is not authorized."
        )


def permitted_own_compensation_report(
    actor,
    start_date,
    end_date,
):
    """Check permission before retrieving any compensation evidence."""

    require_own_compensation_permission(actor)

    return own_individual_compensation_report_with_evidence(
        actor,
        start_date,
        end_date,
    )