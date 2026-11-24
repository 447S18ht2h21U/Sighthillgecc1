"""Assigned Sales Associate adult-ID attestation.

No license number, photograph, or independent signing authorization
is collected or issued by this endpoint.
"""
import re

from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AuditEvent, Project, Role
from .operational_visibility import operational_project_scope
from .services import audit

STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY "
    "LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH "
    "OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
ACTION = "customer.adult_id_attested"
SYNTHETIC_ACTION = "customer.synthetic_adult_test_evidence"
SYNTHETIC_PROJECT_CODES = frozenset({
    "104-SA-2026-11-22",
    "105-SA-2026-11-23",
})


def synthetic_allowed(project):
    import os
    from django.conf import settings
    return (
        settings.DEBUG
        and os.environ.get("GECC_DEV") == "1"
        and project.code in SYNTHETIC_PROJECT_CODES
    )


def verified_row(project):
    return (
        AuditEvent.objects.filter(
            action__in=([ACTION, SYNTHETIC_ACTION] if synthetic_allowed(project) else [ACTION]),
            entity_id=project.pk,
            actor_id=project.sales_associate_id,
            payload__approved_msr_id=str(project.current_approved_id),
        )
        .order_by("-sequence")
        .first()
    )


def public_status(event):
    if event is None:
        return {"recorded": False}
    return {
        "recorded": True,
        "synthetic": event.action == SYNTHETIC_ACTION,
        "evidence_id": str(event.pk),
        "employee_id": str(event.actor_id),
        "state_of_issue": event.payload["state_of_issue"],
        "approved_msr_id": event.payload["approved_msr_id"],
        "adult_confirmed": True,
        "timestamp": event.payload["recorded_at"],
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def adult_verification(request, project_id):
    actor = request.user
    project = (
        operational_project_scope(actor)
        .select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )
    if project is None:
        raise PermissionDenied("Project is not available.")

    if request.method == "GET":
        return Response({**public_status(verified_row(project)), "synthetic_available": synthetic_allowed(project)})

    if (
        not actor.is_active
        or actor.role != Role.SALES_ASSOCIATE
        or project.sales_associate_id != actor.pk
    ):
        raise PermissionDenied(
            "Only the assigned Sales Associate may record this check."
        )

    if not isinstance(request.data, dict):
        raise ValidationError("Invalid verification request.")

    synthetic = request.data == {"synthetic": True}
    if synthetic:
        if not synthetic_allowed(project):
            raise PermissionDenied(
                "Synthetic verification is restricted to the fictional development project."
            )
        state = "SYNTHETIC"
    else:
        allowed = {"state_of_issue", "adult_confirmed"}
        if set(request.data) != allowed:
            raise ValidationError(
                "Submit only issuing state and adult confirmation. "
                "Do not submit identification numbers or images."
            )
        state = request.data.get("state_of_issue")
        if not isinstance(state, str) or state not in STATES:
            raise ValidationError({"state_of_issue": "Choose a valid state."})
        if request.data.get("adult_confirmed") is not True:
            raise ValidationError(
                {"adult_confirmed": "An actual in-person check is required."}
            )

    from django.utils import timezone

    with transaction.atomic():
        project = (
            Project.objects.select_for_update()
            .select_related("current_approved")
            .get(pk=project.pk)
        )
        if project.sales_associate_id != actor.pk:
            raise PermissionDenied("Project assignment changed.")
        if synthetic and not synthetic_allowed(project):
            raise PermissionDenied("Synthetic project eligibility changed.")

        if (
            project.current_approved is None
            or project.current_approved.status != "APPROVED"
            or project.state == "CANCELLED"
        ):
            raise ValidationError(
                "An active project with an approved MSR is required."
            )

        existing = verified_row(project)
        if existing is not None:
            if existing.payload["state_of_issue"] != state:
                raise ValidationError(
                    "An attestation is already recorded for this MSR. "
                    "A correction needs separate review."
                )
            return Response(public_status(existing), status=200)

        payload = {
            "project_id": str(project.pk),
            "approved_msr_id": str(project.current_approved_id),
            "employee_id": str(actor.pk),
            "state_of_issue": state,
            "adult_confirmed": True,
            "verification_method": (
                "SYNTHETIC_BROWSER_ACCEPTANCE"
                if synthetic else "IN_PERSON_PHOTO_ID"
            ),
            "synthetic": synthetic,
            "recorded_at": timezone.now().isoformat(),
            "scope": (
                "FICTIONAL_TEST_ONLY_NOT_IDENTITY_EVIDENCE"
                if synthetic else "AGE_ONLY_NOT_SIGNING_AUTHORITY"
            ),
        }
        event = audit(actor, SYNTHETIC_ACTION if synthetic else ACTION, project.pk, payload)
        return Response(public_status(event), status=201)
