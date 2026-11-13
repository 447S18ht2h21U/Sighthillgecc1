"""Manager-only CSV preview and confirmed import; isolated execution only."""
import hashlib

from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.http import Http404
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from .models import ProductCatalogCollection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .catalog_bulk_import_service_4670 import (
    MAX_BYTES,
    _require_isolated_import,
    _require_persistent_import_authorization,
    import_catalog_csv,
    import_catalog_csv_persistent,
    preview_catalog_csv,
)
from .equipment_catalog_policy import manager_may_manage_equipment
from .fictional_document_preview_api_4525 import development_preview_enabled


def _authorized(request):
    if (
        not development_preview_enabled()
        or request.get_host().split(":")[0]
        not in ("localhost", "127.0.0.1", "testserver")
    ):
        raise Http404()
    if not manager_may_manage_equipment(request.user):
        raise PermissionDenied("Catalog manager authorization required.")


def _available():
    try:
        name = str(connection.settings_dict.get("NAME", ""))
        if name in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        ):
            _require_isolated_import()
        else:
            _require_persistent_import_authorization()
        return True
    except RuntimeError:
        return False


def _preview_available():
    # Only the existing local-development manager API can call this.
    # Schema availability does not authorize persistent writes.
    try:
        ProductCatalogCollection.objects.exists()
        return True
    except (OperationalError, ProgrammingError):
        return False


def _input(data):
    if type(data) is not dict or set(data) != {
        "action", "name", "description", "csv_text",
        "catalog_id", "confirmation",
    }:
        raise ValidationError("Unexpected CSV import parameters.")

    action = data["action"]
    if action not in ("preview", "import"):
        raise ValidationError("Action must be preview or import.")

    csv_text = data["csv_text"]
    if type(csv_text) is not str:
        raise ValidationError("CSV text is required.")

    content = csv_text.encode("utf-8")
    if not 0 < len(content) <= MAX_BYTES:
        raise ValidationError("CSV size is not permitted.")

    name = data["name"]
    description = data["description"]
    catalog_id = data["catalog_id"]

    if catalog_id is not None:
        if (
            type(catalog_id) is not str
            or len(catalog_id) != 36
            or name is not None
            or description is not None
        ):
            raise ValidationError("Invalid existing catalog target.")
    elif type(name) is not str or type(description) is not str:
        raise ValidationError("A catalog name and description are required.")

    # Bind confirmation to the file and exact catalog target.
    material = "\n".join((
        name or "",
        description or "",
        catalog_id or "",
        csv_text,
    )).encode("utf-8")
    confirmation = hashlib.sha256(material).hexdigest()

    return {
        "action": action,
        "content": content,
        "name": name,
        "description": description,
        "catalog_id": catalog_id,
        "confirmation": confirmation,
        "supplied_confirmation": data["confirmation"],
    }


def _execute(call):
    try:
        return call()
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except (DjangoValidationError, ValueError) as exc:
        detail = (
            exc.messages
            if isinstance(exc, DjangoValidationError)
            else str(exc)
        )
        raise ValidationError(detail) from exc


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def bulk_csv(request):
    _authorized(request)
    import_available = _available()
    preview_available = _preview_available()

    if request.method == "GET":
        response = Response({
            "available": preview_available,
            "import_available": import_available,
            "max_bytes": MAX_BYTES,
            "max_rows": 500,
            "required_columns": [
                "brand",
                "residential_system_type",
                "model_number",
                "description",
            ],
            "reason": (
                "CSV preview and authorized catalog import are available."
                if import_available else
                "CSV preview is available. Persistent imports require separate authorization."
                if preview_available else
                "Catalog schema is unavailable; preview and import disabled."
            ),
        })
        response["Cache-Control"] = "private, no-store"
        return response

    if not preview_available:
        raise Http404()

    values = _input(request.data)

    kwargs = {
        "actor_id": request.user.pk,
        "content": values["content"],
        "name": values["name"],
        "description": values["description"],
        "catalog_id": values["catalog_id"],
    }

    if values["action"] == "preview":
        if values["supplied_confirmation"] is not None:
            raise ValidationError("Preview cannot include confirmation.")
        preview = _execute(lambda: preview_catalog_csv(**kwargs))
        response = Response({
            **preview,
            "confirmation": values["confirmation"],
            "persistent_activation": False,
        })
    else:
        if not import_available:
            raise Http404()
        if (
            type(values["supplied_confirmation"]) is not str
            or values["supplied_confirmation"] != values["confirmation"]
        ):
            raise ValidationError(
                "Preview confirmation does not match this CSV and catalog."
            )
        name = str(connection.settings_dict.get("NAME", ""))
        if name in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        ):
            operation = import_catalog_csv
        else:
            operation = import_catalog_csv_persistent

        catalog, added = _execute(lambda: operation(**kwargs))
        response = Response({
            "catalog_id": str(catalog.pk),
            "catalog_name": catalog.name,
            "added": added,
            "persistent_activation": False,
        }, status=status.HTTP_201_CREATED)

    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
