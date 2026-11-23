"""Read-only, project-scoped MSR draft audit history."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .api import project_scope
from .models import AuditEvent, User


@api_view(["GET"])
def draft_history(request, project_id):
    actor = User.objects.get(pk=request.user.pk)

    if not actor.is_active:
        raise PermissionDenied("An active account is required.")

    # Scope is enforced server-side, not merely in the browser.
    project = get_object_or_404(
        project_scope(actor), pk=project_id
    )

    events = (
        AuditEvent.objects
        .filter(entity_id=project.pk, action="msr.edit")
        .select_related("actor")
        .order_by("-sequence")[:50]
    )

    entries = []
    for event in events:
        payload = event.payload
        entries.append({
            "id": str(event.id),
            "sequence": event.sequence,
            "msr_id": payload.get("msr_id"),
            "version": payload.get("version"),
            "edit_sequence": payload.get("edit_sequence"),
            "actor_name": (
                event.actor.get_full_name().strip()
                or event.actor.username
            ),
            "actor_role": event.actor.role,
            "saved_at": event.created_at.isoformat(),
            "changed_fields": payload.get("changed_fields"),
            "snapshot": payload.get("after", payload.get("snapshot")),
            "has_explicit_comparison": (
                "changed_fields" in payload
                and "before" in payload
            ),
        })

    response = Response({
        "project_id": str(project.id),
        "entries": entries,
        "limit": 50,
        "more_available": (
            AuditEvent.objects.filter(
                entity_id=project.pk, action="msr.edit"
            ).count() > 50
        ),
    })
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
