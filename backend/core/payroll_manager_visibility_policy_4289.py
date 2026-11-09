"""Non-operational manager payroll visibility classification.

This is a planning policy, NOT authorization. A verified immutable
historical classification will be needed before operational use.

Free-text contractor job descriptions and current account roles
must not establish historical payroll classification.

No database reads, API registration, or permission grants.
"""

from .models import Role


MANAGER_SUBJECT_ROLES = {
    Role.SALES_MANAGER: frozenset({Role.SALES_ASSOCIATE}),
    Role.INSTALLATION_MANAGER: frozenset({Role.TECHNICIAN}),
}

EXECUTIVE_READ_ROLES = frozenset({
    Role.CEO,
    Role.COMPTROLLER,
})

KNOWN_SUBJECT_ROLES = frozenset(value for value, _ in Role.choices)


def candidate_manager_payroll_visibility(
    *,
    viewer_role,
    subject_role,
    historical_binding_verified,
):
    """Classify a proposed view without granting effective access.

    Both role strings must originate from trusted records at a
    future, separately authorized boundary. A caller-supplied
    True flag is NOT independent historical verification.
    """

    if historical_binding_verified is not True:
        return False

    if not isinstance(viewer_role, str):
        return False

    if not isinstance(subject_role, str):
        return False

    if subject_role not in KNOWN_SUBJECT_ROLES:
        return False

    if viewer_role in EXECUTIVE_READ_ROLES:
        return True

    return subject_role in MANAGER_SUBJECT_ROLES.get(
        viewer_role, frozenset()
    )


def manager_payroll_live_access(*args, **kwargs):
    """Always deny until real authorization and history are verified."""
    return False