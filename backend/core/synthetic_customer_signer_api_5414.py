"""Fictional customer-signer request and independent approval API.

Development-only browser acceptance. No real customer identity, signing
authority, provider delivery, or production approval is asserted.
"""
from django.conf import settings
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AuditEvent,
    CustomerSignerAuthorization,
    Project,
    Role,
)
from .operational_visibility import operational_project_scope
from .services import audit
from .customer_signer_authorization_services import (
    approve_customer_signer,
    require_approved_customer_signer,
)

PROJECT_CODES = frozenset({
    "104-SA-2026-11-22",
    "105-SA-2026-11-23",
})
REQUEST_ACTION = "customer.synthetic_signer_authorization_requested"
GROUP = "COMMERCIAL"


def require_fictional_project(actor, project_id):
    import os

    if (
        not settings.DEBUG
        or os.environ.get("GECC_DEV") != "1"
        or os.environ.get("VERIDIAN_ENVIRONMENT") != "development"
        or os.environ.get("PGHOST")
        or settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"
    ):
        raise PermissionDenied(
            "Synthetic authorization is unavailable outside local development."
        )

    project = (
        operational_project_scope(actor)
        .select_related("current_approved", "customer")
        .filter(pk=project_id, code__in=PROJECT_CODES)
        .first()
    )
    if project is None:
        raise PermissionDenied("Fictional acceptance project is unavailable.")

    if (
        project.current_approved_id is None
        or project.current_approved.status != "APPROVED"
        or project.state == "CANCELLED"
    ):
        raise ValidationError("An active approved fictional MSR is required.")

    return project


def active_request(project):
    return (
        AuditEvent.objects.filter(
            action=REQUEST_ACTION,
            entity_id=project.pk,
            actor_id=project.sales_associate_id,
            payload__approved_msr_id=str(project.current_approved_id),
        )
        .order_by("-sequence")
        .first()
    )


def existing_approval(project, request_event):
    payload = request_event.payload
    return (
        CustomerSignerAuthorization.objects.filter(
            project=project,
            approved_msr_id=project.current_approved_id,
            customer=project.customer,
            group=GROUP,
            requested_by_id=request_event.actor_id,
            signer_name=payload["signer_name"],
            signer_email__iexact=payload["signer_email"],
            evidence_reference=str(request_event.pk),
            revocation__isnull=True,
        )
        .order_by("-approved_at")
        .first()
    )


def response_data(project):
    request_event = active_request(project)
    if request_event is None:
        return {
            "requested": False,
            "approved": False,
            "synthetic": True,
        }

    approval = existing_approval(project, request_event)

    return {
        "requested": True,
        "approved": approval is not None,
        "synthetic": True,
        "request_id": str(request_event.pk),
        "requested_by_id": str(request_event.actor_id),
        "requested_at": request_event.payload["requested_at"],
        "approved_msr_id": request_event.payload["approved_msr_id"],
        "signer_name": request_event.payload["signer_name"],
        "signer_email": request_event.payload["signer_email"],
        "authorization_id": str(approval.pk) if approval else None,
        "approved_by_id": str(approval.approved_by_id) if approval else None,
        "approved_at": approval.approved_at.isoformat() if approval else None,
        "description": (
            "SYNTHETIC TEST AUTHORIZATION - FICTIONAL PROJECT ONLY"
        ),
    }



def controlled_sandbox_recipient_5602(email):
    """Permit a real inbox only when explicitly allowlisted in development."""
    import os
    from .signing_test import address

    raw = os.getenv("GECC_COMMERCIAL_SANDBOX_TEST_EMAILS", "")
    entries = [item.strip() for item in raw.split(",")]

    if not 2 <= len(entries) <= 10 or any(not item for item in entries):
        raise ValidationError(
            "Configure two to ten controlled sandbox recipient addresses."
        )

    allowed = [address(item) for item in entries]

    if len(set(allowed)) != len(allowed):
        raise ValidationError(
            "Controlled sandbox recipient addresses must be distinct."
        )

    if email not in allowed:
        raise ValidationError({
            "signer_email":
                "This address is not in the controlled sandbox recipient allowlist."
        })

    return email


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status(request, project_id):
    project = require_fictional_project(request.user, project_id)
    return Response(response_data(project))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_authorization(request, project_id):
    actor = request.user

    if (
        not actor.is_active
        or actor.role != Role.SALES_ASSOCIATE
    ):
        raise PermissionDenied(
            "Only the assigned Sales Associate can request signing authority."
        )

    project = require_fictional_project(actor, project_id)

    if project.sales_associate_id != actor.pk:
        raise PermissionDenied("The Sales Associate is not assigned to this project.")

    if not isinstance(request.data, dict):
        raise ValidationError("A JSON object is required.")

    if set(request.data) != {"signer_name", "signer_email"}:
        raise ValidationError(
            "Enter only the fictional signer name and test email."
        )

    name = request.data.get("signer_name")
    email = request.data.get("signer_email")

    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 250:
        raise ValidationError({"signer_name": "Enter a fictional signer name."})

    if not isinstance(email, str) or len(email.strip()) > 254:
        raise ValidationError({"signer_email": "Enter a valid fictional email."})

    email = email.strip().lower()
    if not email.endswith("@example.invalid"):
        controlled_sandbox_recipient_5602(email)

    try:
        validate_email(email)
    except DjangoValidationError:
        raise ValidationError({"signer_email": "Invalid fictional email."})

    from django.utils import timezone

    with transaction.atomic():
        project = (
            Project.objects.select_for_update()
            .select_related("current_approved", "customer")
            .get(pk=project.pk)
        )

        require_fictional_project(actor, project.pk)

        if project.sales_associate_id != actor.pk:
            raise PermissionDenied("Project assignment changed.")

        existing = active_request(project)
        if existing is not None:
            same_identity = (
                existing.payload["signer_name"] == name.strip()
                and existing.payload["signer_email"] == email
            )

            if same_identity:
                return Response(response_data(project), status=200)

            if existing_approval(project, existing) is None:
                raise ValidationError(
                    "The current synthetic request is awaiting independent "
                    "approval. Do not replace a pending request."
                )

            # Historical requests and approvals remain immutable.
            # A different signer requires a new request and fresh approval.

        audit(
            actor,
            REQUEST_ACTION,
            project.pk,
            {
                "project_id": str(project.pk),
                "approved_msr_id": str(project.current_approved_id),
                "signer_name": name.strip(),
                "signer_email": email,
                "requested_by_id": str(actor.pk),
                "requested_at": timezone.now().isoformat(),
                "synthetic": True,
                "scope": "FICTIONAL_TEST_AUTHORITY_REQUEST_ONLY",
            },
        )

        return Response(response_data(project), status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_authorization(request, project_id):
    actor = request.user

    if not actor.is_active or actor.role != Role.SALES_MANAGER:
        raise PermissionDenied(
            "Only the assigned Sales Manager may approve this synthetic request."
        )

    if request.data != {"approve": True}:
        raise ValidationError(
            "Explicit synthetic approval confirmation is required."
        )

    project = require_fictional_project(actor, project_id)

    if project.reviewer_id != actor.pk:
        raise PermissionDenied("Only the assigned Sales Manager may approve.")

    with transaction.atomic():
        project = (
            Project.objects.select_for_update()
            .select_related("current_approved", "customer")
            .get(pk=project.pk)
        )

        require_fictional_project(actor, project.pk)

        if project.reviewer_id != actor.pk:
            raise PermissionDenied("Project reviewer changed.")

        request_event = active_request(project)
        if request_event is None:
            raise ValidationError(
                "The Sales Associate must first submit a synthetic request."
            )

        existing = existing_approval(project, request_event)
        if existing is not None:
            return Response(response_data(project), status=200)

        requester = request_event.actor
        if not requester.is_active or requester.role != Role.SALES_ASSOCIATE:
            raise PermissionDenied("The original requester is no longer eligible.")

        payload = request_event.payload
        approve_customer_signer(
            project=project,
            customer=project.customer,
            group=GROUP,
            signer_name=payload["signer_name"],
            signer_email=payload["signer_email"],
            authority_basis=(
                "SYNTHETIC TEST ONLY - fictional signer authorization "
                "for browser acceptance, not real customer authority"
            ),
            evidence_reference=str(request_event.pk),
            requested_by=requester,
            approved_by=actor,
        )

        return Response(response_data(project), status=201)
