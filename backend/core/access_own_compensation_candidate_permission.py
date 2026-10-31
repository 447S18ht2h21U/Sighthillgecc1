"""Candidate effective role decision for own compensation only.

NOT connected to has_permission, production API routing, or service grants.
This provides an independently testable integration candidate.
Authentication must be established by Django before calling this helper.
"""

from .access_own_compensation_role_policy import OWN_COMPENSATION_CODE
from .access_own_compensation_verified_identity import (
    verified_own_compensation_role_eligible,
)


def candidate_own_compensation_allowed(actor, code, *, project=None):
    """Require the exact permission and verified current database identity."""
    if code != OWN_COMPENSATION_CODE or project is not None:
        return False

    return verified_own_compensation_role_eligible(actor)


def candidate_permission_is_live():
    """The candidate remains disconnected from operational authorization."""
    return False