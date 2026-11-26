"""Isolated fictional installation scheduling.

Persist a clearly classified acceptance appointment in immutable
project evidence. Never create an operational InstallationSchedule.
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Project,
    ProjectEvidence,
    Role,
    User,
)

from .documents import canonical_hash
from .services import audit

from .fictional_installation_readiness_5945 import (
    assess_fictional_installation,
    PROJECT_ID,
    MSR_ID,
    ATTEMPT_ID,
    OBSERVATION_ID,
    APPROVED_TEST_DATE,
)

EVIDENCE_KIND = "FICTIONAL_INSTALL_SCHEDULE"


def _existing(msr):
    return ProjectEvidence.objects.filter(
        msr=msr,
        kind=EVIDENCE_KIND,
    ).order_by("-created_at", "-pk").first()


@transaction.atomic
def schedule_fictional_installation(
    *,
    actor,
    project_id,
    installation_manager_id,
    confirmed,
):
    if confirmed is not True:
        raise ValidationError(
            "Explicit fictional appointment confirmation is required."
        )

    if actor is None or not actor.is_authenticated:
        raise PermissionDenied("Authenticated employee required.")

    actor = User.objects.filter(
        pk=actor.pk,
        is_active=True,
        role__in=[
            Role.COMPTROLLER,
            Role.INSTALLATION_MANAGER,
        ],
    ).first()

    if actor is None:
        raise PermissionDenied(
            "An active Comptroller or Installation Manager is required."
        )

    readiness = assess_fictional_installation(
        actor=actor,
        project_id=project_id,
    )

    if readiness["fictional_scheduling_candidate"] is not True:
        raise ValidationError(
            "Fictional installation requirements are incomplete."
        )

    project = Project.objects.select_for_update().get(
        pk=PROJECT_ID,
        current_approved_id=MSR_ID,
    )

    manager = User.objects.filter(
        pk=installation_manager_id,
        is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()

    if manager is None:
        raise ValidationError(
            "An active Installation Manager is required."
        )

    if (
        actor.role == Role.INSTALLATION_MANAGER
        and actor.pk != manager.pk
    ):
        raise PermissionDenied(
            "An Installation Manager may schedule this test only for themselves."
        )

    existing = _existing(project.current_approved)

    if existing is not None:
        raise ValidationError(
            "A fictional appointment already exists for this MSR."
        )

    data = {
        "classification": "FICTIONAL_ACCEPTANCE_ONLY",
        "project_id": PROJECT_ID,
        "msr_id": MSR_ID,
        "commercial_attempt_id": ATTEMPT_ID,
        "provider_observation_id": OBSERVATION_ID,
        "scheduled_date": APPROVED_TEST_DATE.isoformat(),
        "installation_manager_id": str(manager.pk),
        "scheduled_by_id": str(actor.pk),
        "status": "FICTIONAL_SCHEDULED",
        "readiness": readiness,
        "operational_schedule_created": False,
        "installation_authorized": False,
        "installation_started": False,
    }

    record = ProjectEvidence.objects.create(
        msr=project.current_approved,
        kind=EVIDENCE_KIND,
        created_by=actor,
        data=data,
        digest=canonical_hash(data),
    )

    audit(
        actor,
        "fictional_installation.scheduled",
        record.pk,
        data,
    )

    return record


def fictional_schedule_status(*, actor, project_id):
    readiness = assess_fictional_installation(
        actor=actor,
        project_id=project_id,
    )

    project = Project.objects.get(pk=PROJECT_ID)
    record = _existing(project.current_approved)

    appointment = None

    if record is not None:
        if canonical_hash(record.data) != record.digest:
            raise ValidationError(
                "Fictional appointment integrity verification failed."
            )

        data = record.data

        if (
            data.get("classification")
                != "FICTIONAL_ACCEPTANCE_ONLY"
            or data.get("project_id") != PROJECT_ID
            or data.get("msr_id") != MSR_ID
            or data.get("operational_schedule_created") is not False
            or data.get("installation_authorized") is not False
            or data.get("installation_started") is not False
        ):
            raise ValidationError(
                "Fictional appointment classification is invalid."
            )

        appointment = {
            "id": str(record.pk),
            **data,
        }

    return {
        "fictional_acceptance_only": True,
        "readiness": readiness,
        "appointment": appointment,
        "operational_scheduling_authorized": False,
        "installation_authorized": False,
    }