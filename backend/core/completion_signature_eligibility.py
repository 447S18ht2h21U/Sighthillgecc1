"""Read-only prerequisites for trusted completion verification; not proof of signing."""

from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from . import release


def require_verification_eligibility(actor, package):
    """Require Comptroller authority and a currently approved release package."""
    if actor is None or not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or getattr(actor, "role", None) != Role.COMPTROLLER:
        raise PermissionDenied("Only an active Comptroller may initiate trusted completion verification.")
    if package is None:
        raise ValidationError("A release package is required.")
    if package.plan.group not in ("COMPLETION_FINANCED", "COMPLETION_NON_FINANCED"):
        raise ValidationError("Only completion signing packages qualify for completion verification.")
    release.validate_package(package, check_current=True)
    state = release.status(package)
    if state.get("status") != "APPROVED":
        raise ValidationError("Current approved release authorization is required.")
    return {"release_package_id": str(package.pk), "package_digest": package.digest, "eligible_for_verification_review": True, "provider_verified": False}
