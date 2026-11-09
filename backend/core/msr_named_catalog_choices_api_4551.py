"""Read-only named equipment catalogs for development MSR drafting."""
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .fictional_document_preview_api_4525 import development_preview_enabled
from .models import ProductCatalogCollection, ProductCatalogMembership

READ_ROLES = frozenset({
    "SALES_ASSOCIATE",
    "SALES_MANAGER",
    "INSTALLATION_MANAGER",
    "COMPTROLLER",
})


def _load_catalog_choices():
    catalogs = list(
        ProductCatalogCollection.objects.filter(is_active=True)
        .order_by("name")
        .values("id", "name")[:100]
    )

    if not catalogs:
        return []

    identifiers = [record["id"] for record in catalogs]
    indexed = {
        record["id"]: {
            "id": str(record["id"]),
            "name": record["name"],
            "products": [],
        }
        for record in catalogs
    }

    memberships = (
        ProductCatalogMembership.objects.filter(
            catalog_id__in=identifiers,
            equipment__is_active=True,
        )
        .select_related("equipment")
        .order_by(
            "catalog_id", "equipment__brand",
            "equipment__model_number", "equipment__revision"
        )[:5000]
    )

    for membership in memberships:
        item = membership.equipment
        indexed[membership.catalog_id]["products"].append({
            "id": str(item.pk),
            "brand": item.brand,
            "residential_system_type": item.residential_system_type,
            "model_number": item.model_number,
            "description": item.description,
        })

    return [indexed[record["id"]] for record in catalogs]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def msr_named_catalog_choices(request):
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
        result = _load_catalog_choices()
    except (OperationalError, ProgrammingError):
        response = Response({
            "detail": "Named catalog tables are not available."
        }, status=503)
    else:
        response = Response(result)

    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
