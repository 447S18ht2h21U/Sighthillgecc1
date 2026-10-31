"""Read-only, self-service contractor payment history API foundation.

Do not register this endpoint until independent HTTP authorization tests pass.
This API never creates, approves, issues, or settles contractor payments.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .access_compensation_disclosure import own_contractor_payment_disclosure
from .access_own_contractor_payment_permissions import (
    require_own_contractor_payment_permission as require_own_compensation_permission,
)
from .models import User


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def own_contractor_payment_history(request):
    """Disclose only authorized, approved/paid compensation for this user."""
    supplied_actor = getattr(request, "user", None)
    actor_id = getattr(supplied_actor, "pk", None)

    if (
        supplied_actor is None
        or not getattr(supplied_actor, "is_authenticated", False)
        or actor_id is None
    ):
        raise PermissionDenied("An active account is required.")

    actor = User.objects.filter(
        pk=actor_id,
        is_active=True,
    ).first()

    if actor is None:
        raise PermissionDenied("An active account is required.")

    # Position proposals are not effective permission grants.
    require_own_compensation_permission(actor)

    # The established disclosure helper enforces explicit contractor ownership,
    # suppresses drafts, and returns only an approved field allowlist.
    records = own_contractor_payment_disclosure(actor)

    response = Response({"results": records})
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response