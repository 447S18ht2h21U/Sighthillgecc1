"""Read-only approved-MSR document-source inspection.

Development only. Existing project scope is mandatory.
Does not render, prepare, send, sign or save any customer document.
"""
from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .api import project_scope
from .fictional_document_preview_api_4525 import (
    development_preview_enabled,
)


ALLOWED_ROLES = frozenset({
    "SALES_ASSOCIATE",
    "SALES_MANAGER",
    "COMPTROLLER",
})

FIELDS = (
    "customer",
    "billing_address",
    "project_location",
    "project_city",
    "project_state",
    "project_zip",
    "scope",
    "base_price",
    "discount",
    "tax",
    "total_price",
    "financing_type",
    "payment_option",
)


def approved_source_payload(project):
    """Never substitute a draft, pending or historical MSR version."""
    approved = project.current_approved

    if (
        approved is None
        or approved.project_id != project.id
        or approved.status != "APPROVED"
        or approved.approved_at is None
        or approved.approved_by_id is None
        or not isinstance(approved.number, int)
        or approved.number < 1
        or type(approved.snapshot) is not dict
    ):
        raise Http404()

    values = {}
    for key in FIELDS:
        value = approved.snapshot.get(key, "")
        values[key] = value.strip() if type(value) is str else ""

    if not values["customer"] or not values["project_location"]:
        raise Http404()

    equipment = approved.snapshot.get("equipment")
    equipment_count = len(equipment) if type(equipment) is list else 0

    return {
        "source": "CURRENT_APPROVED_MSR",
        "read_only": True,
        "document_generation_authorized": False,
        "project_id": str(project.id),
        "project_code": project.code,
        "msr_id": str(approved.id),
        "msr_number": approved.number,
        "msr_status": approved.status,
        "fields": values,
        "equipment_count": equipment_count,
        "pending_revision_excluded": True,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def approved_msr_source(request, project_id):
    if not development_preview_enabled():
        raise Http404()

    if request.get_host().split(":")[0] not in (
        "localhost", "127.0.0.1", "testserver"
    ):
        raise Http404()

    actor = request.user
    if (
        not getattr(actor, "is_active", False)
        or getattr(actor, "role", None) not in ALLOWED_ROLES
    ):
        raise Http404()

    # Scope is established by the backend, never by the UI.
    project = (
        project_scope(actor)
        .filter(pk=project_id)
        .select_related("current_approved")
        .first()
    )

    if project is None:
        raise Http404()

    result = Response(approved_source_payload(project))
    result["Cache-Control"] = "no-store, private"
    result["X-Content-Type-Options"] = "nosniff"
    return result
