"""Development-only, read-only equipment catalog choices."""
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .fictional_document_preview_api_4525 import development_preview_enabled
from .models import EquipmentCatalogItem


READ_ROLES = frozenset({
    "SALES_ASSOCIATE",
    "SALES_MANAGER",
    "COMPTROLLER",
    "INSTALLATION_MANAGER",
})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def equipment_catalog_choices(request):
    if not development_preview_enabled():
        raise Http404()

    if request.get_host().split(":")[0] not in (
        "127.0.0.1", "localhost", "testserver"
    ):
        raise Http404()

    actor = request.user
    if (
        not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) not in READ_ROLES
    ):
        raise Http404()

    try:
        rows = list(
            EquipmentCatalogItem.objects.filter(is_active=True)
            .order_by("brand", "residential_system_type", "model_number", "id")
            .values(
                "id", "brand", "residential_system_type",
                "model_number", "description"
            )[:500]
        )
    except (OperationalError, ProgrammingError):
        response = Response({
            "detail": "Equipment catalog database is not activated."
        }, status=503)
    else:
        response = Response([
            {**row, "id": str(row["id"])}
            for row in rows
        ])

    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response
