"""Marketing MSR read-only authorization policy.

This is a policy foundation, not a live API integration.
It never authorizes record modification or financial disclosure.
"""

from .models import Role


MARKETING_MSR_ACTIONS = frozenset({
    "list",
    "retrieve",
})


def marketing_msr_read_permitted(actor, *, action, method):
    """Allow only active Marketing users to request MSR reads.

    Live API integration must revalidate account identity against
    the database before relying on this policy.
    """

    if actor is None:
        return False

    if not getattr(actor, "is_authenticated", False):
        return False

    if not getattr(actor, "is_active", False):
        return False

    if getattr(actor, "role", None) != Role.MARKETING:
        return False

    if method != "GET":
        return False

    return action in MARKETING_MSR_ACTIONS


def marketing_msr_write_permitted(*args, **kwargs):
    """Marketing cannot modify an MSR through this policy."""
    return False


def marketing_msr_financial_access_permitted(*args, **kwargs):
    """Marketing cannot view payroll or financial statements here."""
    return False


def marketing_msr_signing_permitted(*args, **kwargs):
    """Marketing receives no signing authority."""
    return False