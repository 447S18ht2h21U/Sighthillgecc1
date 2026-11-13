"""Development-only manager-authorized Ruud catalog import endpoint."""
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.http import Http404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .equipment_catalog_policy import manager_may_manage_equipment
from .fictional_document_preview_api_4525 import development_preview_enabled
from .ruud_catalog_import_service_4650 import (
    import_ruud_catalog,
    _require_isolated_database,
)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def import_ruud(request):
    if (
        not development_preview_enabled()
        or request.get_host().split(":")[0]
        not in ("localhost", "127.0.0.1", "testserver")
    ):
        raise Http404()

    if not manager_may_manage_equipment(request.user):
        raise PermissionDenied("Catalog manager authorization required.")

    try:
        _require_isolated_database()
        available = True
    except RuntimeError:
        available = False

    if request.method == "GET":
        response = Response({
            "available": available,
            "catalog": "Ruud Residential Systems",
            "system_count": 15,
            "persistent_activation": False,
            "reason": (
                "Isolated development catalog import is available."
                if available else
                "Catalog database activation is pending. "
                "Persistent imports are disabled."
            ),
        })
        response["Cache-Control"] = "private, no-store"
        return response

    if not available:
        raise Http404()

    if type(request.data) is not dict or request.data:
        raise ValidationError("No import parameters are accepted.")

    try:
        catalog, added = import_ruud_catalog(actor_id=request.user.pk)
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except (DjangoValidationError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc

    response = Response(
        {
            "catalog_id": str(catalog.pk),
            "catalog_name": catalog.name,
            "added": added,
            "total": 15,
            "status": "IMPORTED" if added == 15 else "ALREADY_PRESENT",
            "persistent_activation": False,
        },
        status=status.HTTP_201_CREATED if added == 15 else status.HTTP_200_OK,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
