"""Authenticated, default-disabled inspection draft authorization API."""
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from rest_framework.decorators import api_view
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

from core.installation_draft_browser_5185 import authorize as authorize_intent


@api_view(["POST"])
def authorize(request, project_id):
    if not isinstance(request.data, dict):
        raise ValidationError("JSON confirmation object required.")

    allowed = {"confirm_inspection_draft_intent"}

    if set(request.data) != allowed:
        raise ValidationError(
            "Only explicit inspection draft confirmation is accepted."
        )

    if request.data["confirm_inspection_draft_intent"] is not True:
        raise ValidationError("Explicit confirmation is required.")

    try:
        result = authorize_intent(
            actor=request.user,
            project_id=project_id,
            confirmed=True,
        )
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages) from exc

    return Response(result, status=201)