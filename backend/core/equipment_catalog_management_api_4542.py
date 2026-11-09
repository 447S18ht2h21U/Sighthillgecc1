"""Development-only catalog management; existing audited services own writes."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .equipment_catalog_policy import FIELDS, manager_may_manage_equipment
from .equipment_catalog_service import (
    create_equipment, revise_equipment, deactivate_equipment,
)
from .fictional_document_preview_api_4525 import development_preview_enabled
from .models import EquipmentCatalogItem


def _require_manager(request):
    if not development_preview_enabled():
        raise Http404()
    if request.get_host().split(":")[0] not in (
        "localhost", "127.0.0.1", "testserver"
    ):
        raise Http404()
    if not manager_may_manage_equipment(request.user):
        raise PermissionDenied("Equipment catalog manager authorization required.")


def _handle_service(action):
    try:
        result = action()
        return Response({
            "id": str(result.pk),
            "revision": result.revision,
            "is_active": result.is_active,
        })
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except (DjangoValidationError, ValueError) as exc:
        if isinstance(exc, DjangoValidationError):
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        else:
            detail = str(exc)
        raise ValidationError(detail) from exc


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def manage_catalog(request):
    _require_manager(request)
    if request.method == "POST":
        fields = request.data
        if type(fields) is not dict or set(fields) != set(FIELDS):
            raise ValidationError("Exactly four product fields are required.")
        return _handle_service(lambda: create_equipment(
            actor_id=request.user.pk, fields=fields,
        ))
    try:
        rows = list(
            EquipmentCatalogItem.objects.order_by(
                "brand", "residential_system_type",
                "model_number", "-revision"
            ).values(
                "id", "brand", "residential_system_type",
                "model_number", "description", "revision", "is_active"
            )[:1000]
        )
    except (OperationalError, ProgrammingError):
        response = Response({
            "detail": "Equipment catalog database is not activated."
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    else:
        response = Response([
            {**row, "id": str(row["id"])} for row in rows
        ])
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def manage_catalog_item(request, equipment_id):
    _require_manager(request)
    if request.method == "PATCH":
        fields = request.data
        if type(fields) is not dict or set(fields) != set(FIELDS):
            raise ValidationError("Exactly four product fields are required.")
        return _handle_service(lambda: revise_equipment(
            actor_id=request.user.pk,
            equipment_id=equipment_id,
            fields=fields,
        ))
    if type(request.data) is not dict or set(request.data) != {"reason"}:
        raise ValidationError("A documented deactivation reason is required.")
    return _handle_service(lambda: deactivate_equipment(
        actor_id=request.user.pk,
        equipment_id=equipment_id,
        reason=request.data["reason"],
    ))
