"""Local development-only named catalog API, with manager-only writes."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .equipment_catalog_policy import FIELDS, manager_may_manage_equipment
from .fictional_document_preview_api_4525 import development_preview_enabled
from .models import ProductCatalogCollection, ProductCatalogMembership
from .product_catalog_collections_service_4546 import (
    create_named_catalog,
    create_catalog_product,
    revise_catalog_product,
    deactivate_catalog_product,
    deactivate_named_catalog,
)


def _authorize(request):
    if not development_preview_enabled():
        raise Http404()
    if request.get_host().split(":")[0] not in (
        "127.0.0.1", "localhost", "testserver"
    ):
        raise Http404()
    if not manager_may_manage_equipment(request.user):
        raise PermissionDenied("Catalog manager authorization required.")


def _execute(operation):
    try:
        return operation()
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except (DjangoValidationError, ValueError) as exc:
        if isinstance(exc, DjangoValidationError):
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        else:
            detail = str(exc)
        raise ValidationError(detail) from exc


def _response(value, *, created=False):
    return Response(
        value,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        headers={"Cache-Control": "private, no-store"},
    )


def _fields(data):
    if type(data) is not dict or set(data) != set(FIELDS):
        raise ValidationError("Exactly four equipment detail fields are required.")
    return data


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def collections(request):
    _authorize(request)

    if request.method == "POST":
        if type(request.data) is not dict or set(request.data) != {
            "name", "description",
        }:
            raise ValidationError("Catalog name and description are required.")
        result = _execute(lambda: create_named_catalog(
            actor_id=request.user.pk,
            name=request.data["name"],
            description=request.data["description"],
        ))
        return _response({
            "id": str(result.pk),
            "name": result.name,
            "description": result.description,
            "is_active": result.is_active,
        }, created=True)

    try:
        rows = list(
            ProductCatalogCollection.objects.values(
                "id", "name", "description", "is_active"
            ).order_by("name")[:1000]
        )
    except (OperationalError, ProgrammingError):
        return Response(
            {"detail": "Named catalog schema has not been activated."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return _response([{**row, "id": str(row["id"])} for row in rows])


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def collection_detail(request, catalog_id):
    _authorize(request)
    if type(request.data) is not dict or set(request.data) != {"reason"}:
        raise ValidationError("A documented reason is required.")

    result = _execute(lambda: deactivate_named_catalog(
        actor_id=request.user.pk,
        catalog_id=catalog_id,
        reason=request.data["reason"],
    ))
    return _response({
        "id": str(result.pk),
        "is_active": result.is_active,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def collection_products(request, catalog_id):
    _authorize(request)

    if request.method == "POST":
        result = _execute(lambda: create_catalog_product(
            actor_id=request.user.pk,
            catalog_id=catalog_id,
            fields=_fields(request.data),
        ))
        return _response({
            "id": str(result.pk),
            "revision": result.revision,
            "is_active": result.is_active,
        }, created=True)

    try:
        if not ProductCatalogCollection.objects.filter(pk=catalog_id).exists():
            raise ValidationError("Catalog does not exist.")

        memberships = (
            ProductCatalogMembership.objects.filter(catalog_id=catalog_id)
            .select_related("equipment")
            .order_by(
                "equipment__brand",
                "equipment__residential_system_type",
                "equipment__model_number",
                "-equipment__revision",
            )[:1000]
        )
        rows = [
            {
                "id": str(m.equipment_id),
                "brand": m.equipment.brand,
                "residential_system_type": m.equipment.residential_system_type,
                "model_number": m.equipment.model_number,
                "description": m.equipment.description,
                "revision": m.equipment.revision,
                "is_active": m.equipment.is_active,
            }
            for m in memberships
        ]
    except (OperationalError, ProgrammingError):
        return Response(
            {"detail": "Named catalog schema has not been activated."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return _response(rows)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def collection_product_detail(request, catalog_id, equipment_id):
    _authorize(request)

    if request.method == "PATCH":
        result = _execute(lambda: revise_catalog_product(
            actor_id=request.user.pk,
            catalog_id=catalog_id,
            equipment_id=equipment_id,
            fields=_fields(request.data),
        ))
    else:
        if type(request.data) is not dict or set(request.data) != {"reason"}:
            raise ValidationError("A documented reason is required.")
        result = _execute(lambda: deactivate_catalog_product(
            actor_id=request.user.pk,
            catalog_id=catalog_id,
            equipment_id=equipment_id,
            reason=request.data["reason"],
        ))

    return _response({
        "id": str(result.pk),
        "revision": result.revision,
        "is_active": result.is_active,
    })
