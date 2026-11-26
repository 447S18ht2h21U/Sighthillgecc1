"""Local fictional acceptance payment-exception API.

Uses the established CEO payment exception services without
granting operational signature or installation authorization.
"""

import os
from pathlib import Path

from django.conf import settings
from django.db import transaction

from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CEOPaymentException, Project, Role
from .synthetic_customer_signer_api_5414 import require_fictional_project
from .ceo_payment_exception_services import (
    request_payment_exception,
    decide_payment_exception,
)
from .installation_payment_readiness import installation_payment_readiness


PROJECT_ID = "f8a385b5-8e46-4c0c-886a-f8b6d2fc8d05"
MSR_ID = "f555e52f-ae97-4342-982f-dbd42fb0fa62"
PROJECT_CODE = "105-SA-2026-11-23"


def _guard(actor, project_id):
    database = settings.DATABASES["default"]
    expected_database = (
        Path(__file__).resolve().parents[1]
        / "veridian_browser_acceptance.sqlite3"
    ).resolve()

    if (
        not settings.DEBUG
        or os.environ.get("GECC_DEV") != "1"
        or os.environ.get("VERIDIAN_ENVIRONMENT") != "development"
        or os.environ.get("PGHOST")
        or database["ENGINE"] != "django.db.backends.sqlite3"
        or Path(str(database["NAME"])).resolve() != expected_database
        or str(project_id) != PROJECT_ID
        or not actor.is_authenticated
        or not actor.is_active
    ):
        raise PermissionDenied(
            "Fictional payment exception is unavailable."
        )

    if actor.role not in (
        Role.CEO,
        Role.COMPTROLLER,
        Role.SALES_MANAGER,
        Role.SALES_ASSOCIATE,
    ):
        raise PermissionDenied(
            "You cannot access this payment exception."
        )

    # CEO access is limited to this fictional payment decision.
    # The global operational visibility policy remains unchanged.
    if actor.role == Role.CEO:
        project = (
            Project.objects.select_related("current_approved")
            .filter(
                pk=PROJECT_ID,
                code=PROJECT_CODE,
                current_approved_id=MSR_ID,
                current_approved__status="APPROVED",
            )
            .exclude(state="CANCELLED")
            .first()
        )
        if project is None:
            raise PermissionDenied(
                "Fictional payment exception project is unavailable."
            )
        if project.current_approved.project_id != project.pk:
            raise PermissionDenied(
                "The approved MSR does not belong to this project."
            )
    else:
        project = require_fictional_project(actor, project_id)

    if (
        project.code != PROJECT_CODE
        or str(project.current_approved_id) != MSR_ID
        or project.current_approved.snapshot.get("payment_option")
        != "100_PERCENT_COMPLETION"
    ):
        raise PermissionDenied(
            "The approved fictional project baseline has changed."
        )

    if actor.role not in (Role.CEO, Role.COMPTROLLER):
        if actor.pk not in (
            project.sales_associate_id,
            project.reviewer_id,
        ):
            raise PermissionDenied(
                "You are not assigned to this project."
            )

    return project


def _exception(project):
    return CEOPaymentException.objects.filter(
        project=project,
        msr_id=project.current_approved_id,
    ).first()


def _response(actor, project):
    exception = _exception(project)
    readiness = installation_payment_readiness(project)

    may_request = (
        actor.role == Role.COMPTROLLER
        or actor.pk in (
            project.sales_associate_id,
            project.reviewer_id,
        )
    )

    return {
        "fictional_acceptance_only": True,
        "project_id": str(project.pk),
        "msr_id": str(project.current_approved_id),
        "payment_option": readiness["payment_option"],
        "approved_total": str(readiness["approved_total"]),
        "required_deposit": str(readiness["required_deposit"]),
        "payment_ready": readiness["payment_ready"],
        "ceo_exception_valid": readiness["ceo_exception_valid"],
        "explanation": readiness["explanation"],
        "can_request": bool(
            may_request and exception is None
        ),
        "can_decide": bool(
            exception is not None
            and actor.role == Role.CEO
            and exception.requested_by_id != actor.pk
            and exception.status
            == CEOPaymentException.Status.REQUESTED
        ),
        "exception": None if exception is None else {
            "id": str(exception.pk),
            "status": exception.status,
            "request_reason": exception.request_reason,
            "decision_reason": exception.decision_reason,
            "requested_by_id": str(exception.requested_by_id),
            "decided_by_id": (
                str(exception.decided_by_id)
                if exception.decided_by_id else None
            ),
            "decided_at": (
                exception.decided_at.isoformat()
                if exception.decided_at else None
            ),
        },
        "operational_signature_verified": False,
        "installation_authorized": False,
    }


def _reason(data):
    reason = data.get("reason")

    if (
        not isinstance(reason, str)
        or not reason.strip()
        or len(reason.strip()) > 2000
    ):
        raise ValidationError(
            "Enter a reason of 1 to 2000 characters."
        )

    return "FICTIONAL ACCEPTANCE ONLY: " + reason.strip()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def payment_exception(request, project_id):
    actor = request.user
    project = _guard(actor, project_id)

    if request.method == "GET":
        return Response(_response(actor, project))

    if not isinstance(request.data, dict):
        raise ValidationError("A JSON object is required.")

    action = request.data.get("action")

    with transaction.atomic():
        Project.objects.select_for_update().get(pk=project.pk)
        project = _guard(actor, project_id)

        if action == "request":
            if set(request.data) != {"action", "reason"}:
                raise ValidationError("Invalid request fields.")

            request_payment_exception(
                actor=actor,
                project_id=project.pk,
                msr_id=project.current_approved_id,
                reason=_reason(request.data),
            )

        elif action == "decide":
            if set(request.data) != {
                "action", "exception_id", "approve", "reason"
            }:
                raise ValidationError("Invalid decision fields.")

            if actor.role != Role.CEO:
                raise PermissionDenied(
                    "Only an active CEO may decide."
                )

            if type(request.data["approve"]) is not bool:
                raise ValidationError(
                    "An explicit approval decision is required."
                )

            exception = _exception(project)

            if (
                exception is None
                or str(exception.pk)
                != request.data["exception_id"]
            ):
                raise ValidationError(
                    "Payment exception does not match this project."
                )

            decide_payment_exception(
                actor=actor,
                exception_id=exception.pk,
                approve=request.data["approve"],
                reason=_reason(request.data),
            )

        else:
            raise ValidationError(
                "Unsupported payment exception action."
            )

        return Response(_response(actor, project))
