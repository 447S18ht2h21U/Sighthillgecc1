"""Atomic ownership reassignment with irreversible scope invalidation.

This service is NOT connected to any operational API. Reassignment
authorization is deliberately Comptroller-only pending final policy review.
Every caller that later changes Project.sales_associate must use an
equivalently guarded, locked, audited workflow.
"""

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Project, Role, User
from .msr_delegation_models import (
    MSRDelegationRequestProject,
    MSRDelegationProjectInvalidation,
)
from .services import audit


def _valid_id(value):
    return type(value) is UUID and value.int != 0


@transaction.atomic
def reassign_project_with_msr_invalidation(
    *, project_id, new_owner_id, actor_id, reason,
):
    """Change owner/revision, invalidate affected scopes, and audit as one."""
    if (
        not all(_valid_id(value) for value in (
            project_id, new_owner_id, actor_id
        ))
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2000
    ):
        raise PermissionDenied("Invalid project reassignment.")

    project = Project.objects.select_for_update().filter(
        pk=project_id
    ).first()
    if project is None:
        raise PermissionDenied("Project not found.")

    users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in=(actor_id, new_owner_id)).order_by("pk")
    }
    actor = users.get(actor_id)
    new_owner = users.get(new_owner_id)

    if (
        actor is None or actor.role != Role.COMPTROLLER
        or not actor.is_active
        or new_owner is None or new_owner.role != Role.SALES_ASSOCIATE
        or not new_owner.is_active
    ):
        raise PermissionDenied("Reassignment authority denied.")

    old_owner_id = project.sales_associate_id
    old_revision = project.ownership_revision
    if new_owner_id == old_owner_id:
        raise PermissionDenied("A different owner is required.")
    if (
        type(old_revision) is not int or old_revision < 0
        or old_revision >= 9223372036854775807
    ):
        raise PermissionDenied("Invalid ownership revision.")

    # Both request creation and approval lock Project first.
    # A later operational reassignment route must use this same lock order.
    scopes = list(
        MSRDelegationRequestProject.objects.select_for_update()
        .filter(
            project_id=project.pk,
            request__source_associate_id=old_owner_id,
            request__final_decision__result="APPROVED",
            invalidation__isnull=True,
        )
        .select_related("request__final_decision")
        .order_by("pk")
    )

    new_revision = old_revision + 1
    changed_at = timezone.now()
    project.sales_associate = new_owner
    project.ownership_revision = new_revision
    project.save(update_fields=["sales_associate", "ownership_revision"])

    invalidation_ids = []
    for scope in scopes:
        decision = scope.request.final_decision
        invalidation = MSRDelegationProjectInvalidation.objects.create(
            decision=decision,
            scope=scope,
            previous_revision=old_revision,
            new_revision=new_revision,
            invalidated_at=changed_at,
            reason="PROJECT_REASSIGNED",
            evidence_reference=(
                "PROJECT_OWNERSHIP_REVISION:"
                + str(project.pk) + ":" + str(new_revision)
            ),
        )
        invalidation_ids.append(str(invalidation.pk))

    audit(
        actor,
        "msr.project.reassigned",
        project.pk,
        {
            "old_owner_id": str(old_owner_id),
            "new_owner_id": str(new_owner_id),
            "old_revision": old_revision,
            "new_revision": new_revision,
            "invalidation_ids": invalidation_ids,
            "reason": reason.strip(),
        },
    )
    return project


def reassignment_grants_live_msr_access(*args, **kwargs):
    return False