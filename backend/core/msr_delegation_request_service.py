"""Atomic, audited creation of fixed-project MSR delegation requests.

This module has no URL registration and grants no operational permissions.
Only authoritative database records are used for role and project checks.
"""

from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Project, Role, User
from .msr_delegation_models import (
    MSRDelegationRequest,
    MSRDelegationRequestProject,
)
from .services import audit


def valid_request_parameters(
    *, manager_id, recipient_id, source_associate_id,
    project_ids, starts_at, ends_at, reason, now,
):
    identities = (manager_id, recipient_id, source_associate_id)
    if not all(type(value) is UUID and value.int for value in identities):
        return False
    if len(set(identities)) != 3:
        return False

    if not isinstance(project_ids, (tuple, list)):
        return False
    if not 1 <= len(project_ids) <= 100:
        return False
    if not all(type(value) is UUID and value.int for value in project_ids):
        return False
    if len(set(project_ids)) != len(project_ids):
        return False

    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
        return False

    for value in (starts_at, ends_at, now):
        if not isinstance(value, datetime) or timezone.is_naive(value):
            return False

    return starts_at < ends_at and now < ends_at


@transaction.atomic
def create_fixed_msr_delegation_request(
    *, manager_id, recipient_id, source_associate_id,
    project_ids, starts_at, ends_at, reason,
):
    """Persist a fixed snapshot and hash-chained audit event atomically."""
    now = timezone.now()
    if not valid_request_parameters(
        manager_id=manager_id,
        recipient_id=recipient_id,
        source_associate_id=source_associate_id,
        project_ids=project_ids,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        now=now,
    ):
        raise PermissionDenied("Invalid delegation request.")

    project_ids = tuple(project_ids)

    # Project locks serialize this snapshot against a future reassignment
    # service that must acquire the same Project locks.
    projects = list(
        Project.objects.select_for_update()
        .filter(pk__in=project_ids).order_by("pk")
    )
    if len(projects) != len(project_ids):
        raise PermissionDenied("A selected project does not exist.")

    identities = (manager_id, recipient_id, source_associate_id)
    users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in=identities).order_by("pk")
    }
    if len(users) != 3:
        raise PermissionDenied("A delegation participant does not exist.")

    manager = users[manager_id]
    recipient = users[recipient_id]
    source = users[source_associate_id]

    if (
        manager.role != Role.SALES_MANAGER
        or recipient.role != Role.SALES_ASSOCIATE
        or source.role != Role.SALES_ASSOCIATE
        or not manager.is_active
        or not recipient.is_active
    ):
        raise PermissionDenied("Delegation roles or active status invalid.")

    if any(project.sales_associate_id != source_associate_id
           for project in projects):
        raise PermissionDenied("Project ownership does not match the source.")

    if any(
        type(project.ownership_revision) is not int
        or project.ownership_revision < 0
        for project in projects
    ):
        raise PermissionDenied("Project ownership revision invalid.")

    request = MSRDelegationRequest.objects.create(
        manager=manager,
        recipient=recipient,
        source_associate=source,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason.strip(),
        read_only=True,
    )

    MSRDelegationRequestProject.objects.bulk_create([
        MSRDelegationRequestProject(
            request=request,
            project=project,
            owner_revision=project.ownership_revision,
        )
        for project in projects
    ])

    # The audit operation locks AuditHead and writes AuditEvent + Outbox.
    # Any audit exception rolls back the request and every scope row.
    audit(
        manager,
        "msr.delegation.requested",
        request.pk,
        {
            "recipient_id": str(recipient_id),
            "source_associate_id": str(source_associate_id),
            "project_revisions": [
                {
                    "project_id": str(project.pk),
                    "owner_revision": project.ownership_revision,
                }
                for project in projects
            ],
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "read_only": True,
            "reason": reason.strip(),
        },
    )
    return request


def request_creation_grants_live_msr_access(*args, **kwargs):
    """Creating an MSR delegation request never grants access."""
    return False