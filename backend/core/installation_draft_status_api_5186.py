"""Authenticated read-only inspection draft workflow status API."""
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from core.installation_draft_status_5186 import status as inspect_status


@api_view(["GET"])
def status(request, project_id):
    try:
        result = inspect_status(
            actor=request.user,
            project_id=project_id,
        )
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages) from exc

    return Response(result)

@api_view(["GET"])
def unsigned_pdf_preflight(request, project_id):
    """Authorized offline verification, with no PDF download or provider I/O."""
    from core.installation_unsigned_pdf_preflight_5254 import verify_unsigned_pdf

    try:
        result = verify_unsigned_pdf(
            actor=request.user,
            project_id=project_id,
        )
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages) from exc

    response = Response(result)
    response["Cache-Control"] = "private, no-store"
    return response
