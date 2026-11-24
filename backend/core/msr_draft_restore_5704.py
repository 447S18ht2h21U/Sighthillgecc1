"""Controlled restoration of historical MSR draft saves.

No schema migration. Every restoration is a new audited edit.
"""
import copy

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .api import project_scope
from .models import AuditEvent, MSR, Project, User
from .services import audit, authorize, transition


@api_view(["POST"])
def restore_draft(request, project_id):
    actor = User.objects.get(pk=request.user.pk)
    if not actor.is_active:
        raise PermissionDenied("An active account is required.")

    data = request.data
    if not isinstance(data, dict):
        raise ValidationError("Restoration details must be an object.")

    allowed = {"history_entry_id", "expected_msr_id",
               "expected_sequence", "reason"}
    if set(data) - allowed:
        raise ValidationError("Unknown restoration fields.")

    history_id = data.get("history_entry_id")
    expected_msr_id = data.get("expected_msr_id")
    expected_sequence = data.get("expected_sequence")
    reason = data.get("reason")

    if not isinstance(history_id, str) or not history_id.strip():
        raise ValidationError({"history_entry_id": "Select a historical save."})
    if not isinstance(expected_msr_id, str) or not expected_msr_id.strip():
        raise ValidationError({"expected_msr_id": "Current MSR identity is required."})
    if type(expected_sequence) is not int or expected_sequence < 0:
        raise ValidationError({"expected_sequence": "Invalid save sequence."})
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError({"reason": "Enter a restoration reason (up to 2000 characters)."})

    with transaction.atomic():
        project = get_object_or_404(
            project_scope(actor).select_for_update(), pk=project_id
        )
        authorize(actor, project)

        if project.state == "CANCELLED" or not project.pending_id:
            raise ValidationError("This project has no editable MSR draft.")

        record = MSR.objects.select_for_update().get(pk=project.pending_id)

        if str(record.id) != expected_msr_id:
            raise ValidationError({
                "conflict": "The active MSR version changed. Refresh the project."
            })
        if expected_sequence != record.edit_sequence:
            raise ValidationError({
                "conflict": "This draft changed. Refresh before restoring."
            })
        if record.status not in ("DRAFT", "REJECTED"):
            raise ValidationError(
                "Only a draft or rejected MSR can be restored."
            )

        source = get_object_or_404(
            AuditEvent,
            pk=history_id,
            entity_id=project.id,
            action="msr.edit",
        )
        payload = source.payload
        if not isinstance(payload, dict):
            raise ValidationError("Historical save data is invalid.")

        if (payload.get("msr_id") != str(record.id)
                or payload.get("version") != record.number):
            raise ValidationError(
                "Historical save must belong to the current MSR version."
            )

        restored_snapshot = payload.get(
            "after", payload.get("snapshot")
        )
        if not isinstance(restored_snapshot, dict):
            raise ValidationError("Historical save has no valid snapshot.")

        before = copy.deepcopy(record.snapshot)

        # The existing transition service applies the normal authorization,
        # concurrency, catalog, snapshot validation and audit safeguards.
        saved = transition(
            actor, record.id, "edit", expected_sequence,
            snapshot=copy.deepcopy(restored_snapshot),
            reason=reason.strip(),
        )

        # Additional immutable provenance links the new save to its source.
        audit(actor, "msr.draft_restored", project.id, {
            "msr_id": str(saved.id),
            "version": saved.number,
            "edit_sequence": saved.edit_sequence,
            "source_audit_id": str(source.id),
            "source_audit_sequence": source.sequence,
            "source_edit_sequence": payload.get("edit_sequence"),
            "reason": reason.strip(),
            "before": before,
            "after": copy.deepcopy(saved.snapshot),
        })

    response = Response({
        "project_id": str(project.id),
        "msr_id": str(saved.id),
        "version": saved.number,
        "edit_sequence": saved.edit_sequence,
        "source_history_entry_id": str(source.id),
        "message": "Historical draft restored as a new audited save.",
    })
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
