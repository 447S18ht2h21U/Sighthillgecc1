"""Explicit, development-only inspection DocuSign OAuth initiation API.

Comptroller authentication, approved project and retained evidence
association are enforced by the service. A successful POST starts only
an OAuth challenge, never a DocuSign envelope or installation action.
"""
from uuid import UUID

from django.db import connections, router
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .docusign_api import private
from .installation_provider_oauth_4979 import (
    _gate,
    begin,
)
from .models import (
    InstallationInspectionEvidence4969,
    ProjectEvidence,
)


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical binding UUID required.")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(
            "Canonical binding UUID required."
        ) from None
    return value


@api_view(["POST"])
def connect(request, project_id):
    # Authorization happens before any feature, schema or record details.
    reviewer = _gate(request.user)

    data = request.data
    if type(data) is not dict or set(data) != {
        "binding_id", "sandbox_read_confirmed"
    }:
        raise ValidationError(
            "Binding ID and explicit sandbox-read confirmation required."
        )
    if data["sandbox_read_confirmed"] is not True:
        raise ValidationError(
            "Explicit sandbox-read confirmation required."
        )
    binding_id = _uuid(data["binding_id"])

    # Operational schema may not yet have been migrated.
    # Never migrate it from an API request.
    for model in (
        InstallationInspectionEvidence4969,
        ProjectEvidence,
    ):
        alias = router.db_for_read(model)
        connection = connections[alias]
        with connection.cursor() as cursor:
            if model._meta.db_table not in set(
                connection.introspection.table_names(cursor)
            ):
                raise ValidationError(
                    "Inspection evidence storage unavailable pending "
                    "controlled migration."
                )

    session = getattr(request, "session", None)
    session_key = getattr(session, "session_key", None)
    if type(session_key) is not str or not session_key:
        raise ValidationError(
            "Authenticated browser session required."
        )

    result = begin(
        actor=reviewer,
        project_id=str(project_id),
        binding_id=binding_id,
        session_key=session_key,
    )
    if (
        type(result) is not dict
        or result.get("operation") != "SANDBOX_INSPECTION_READ"
        or result.get("send_enabled") is not False
        or result.get("provider_signature_verified") is not False
        or result.get("project_completion_authorized") is not False
    ):
        raise ValidationError(
            "Inspection OAuth challenge safety contract failed."
        )

    return private(Response(result))
