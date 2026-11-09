"""Atomic final approval for fixed-project MSR delegation evidence.

Not registered as a live API endpoint. Call only after a separately audited
request-creation workflow is implemented and reviewed. Existing MSR
visibility policy remains independent and does not consume this evidence.
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
    MSRDelegationDecision,
)
from .services import audit


def _uuid(value):
    return type(value) is UUID and value.int != 0


def validate_locked_approval_evidence(
    request, scopes, projects, users, approver_id, now
):
    """Fail-closed validation of records loaded from the database."""
    if request is None or not _uuid(approver_id):
        return False
    identities = (
        request.manager_id,
        request.recipient_id,
        request.source_associate_id,
        approver_id,
    )
    if not all(_uuid(value) for value in identities):
        return False
    if len(set(identities)) != 4:
        return False
    if set(users) != set(identities):
        return False

    manager = users[request.manager_id]
    recipient = users[request.recipient_id]
    source = users[request.source_associate_id]
    approver = users[approver_id]

    if (
        manager.role != Role.SALES_MANAGER
        or recipient.role != Role.SALES_ASSOCIATE
        or source.role != Role.SALES_ASSOCIATE
        or approver.role not in (Role.CEO, Role.COMPTROLLER)
    ):
        return False

    if not all(
        type(user.is_active) is bool and user.is_active
        for user in (manager, recipient, approver)
    ):
        return False

    if request.read_only is not True:
        return False
    if not isinstance(now, datetime) or timezone.is_naive(now):
        return False
    if any(
        not isinstance(value, datetime) or timezone.is_naive(value)
        for value in (request.starts_at, request.ends_at)
    ):
        return False
    if not request.starts_at < request.ends_at or now >= request.ends_at:
        return False

    if not isinstance(request.reason, str):
        return False
    if not 10 <= len(request.reason.strip()) <= 2000:
        return False

    if not 1 <= len(scopes) <= 100:
        return False
    if len(projects) != len(scopes):
        return False

    seen = set()
    for scope in scopes:
        if scope.request_id != request.pk or not _uuid(scope.project_id):
            return False
        if scope.project_id in seen:
            return False
        seen.add(scope.project_id)

        project = projects.get(scope.project_id)
        if project is None:
            return False
        if project.sales_associate_id != request.source_associate_id:
            return False
        if (
            type(scope.owner_revision) is not int
            or type(project.ownership_revision) is not int
            or scope.owner_revision < 0
            or scope.owner_revision != project.ownership_revision
        ):
            return False

    return set(projects) == seen


@transaction.atomic
def approve_fixed_msr_delegation(*, request_id, approver_id, reason):
    """Create one immutable decision and an audit event, or roll back."""
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
        raise PermissionDenied("A documented approval reason is required.")

    # Read only the fixed scope IDs before acquiring locks. All evidence is
    # reloaded and checked after the project locks have been acquired.
    reference = MSRDelegationRequest.objects.get(pk=request_id)
    initial_ids = tuple(
        MSRDelegationRequestProject.objects.filter(
            request_id=reference.pk
        ).values_list("project_id", flat=True)
    )
    if not 1 <= len(initial_ids) <= 100:
        raise PermissionDenied("Invalid fixed-project delegation scope.")

    projects = {
        project.pk: project
        for project in Project.objects.select_for_update()
        .filter(pk__in=initial_ids).order_by("pk")
    }

    request = MSRDelegationRequest.objects.select_for_update().get(
        pk=reference.pk
    )
    scopes = list(
        MSRDelegationRequestProject.objects.select_for_update()
        .filter(request_id=request.pk).order_by("project_id")
    )

    if (
        len(initial_ids) != len(scopes)
        or set(initial_ids) != {scope.project_id for scope in scopes}
        or MSRDelegationDecision.objects.filter(request_id=request.pk).exists()
    ):
        raise PermissionDenied("Delegation evidence changed or was decided.")

    ids = (
        request.manager_id, request.recipient_id,
        request.source_associate_id, approver_id,
    )
    users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in=ids).order_by("pk")
    }

    now = timezone.now()
    if not validate_locked_approval_evidence(
        request, scopes, projects, users, approver_id, now
    ):
        raise PermissionDenied("Delegation authority or scope is invalid.")

    approver = users[approver_id]
    decision = MSRDelegationDecision.objects.create(
        request=request,
        decided_by=approver,
        result=MSRDelegationDecision.Result.APPROVED,
        decided_at=now,
        reason=reason.strip(),
        authority_reference="INDEPENDENT_CEO_OR_COMPTROLLER",
    )

    # Existing hash-chain + Outbox; any exception rolls back the decision.
    audit(
        approver,
        "msr.delegation.approved",
        decision.pk,
        {
            "request_id": str(request.pk),
            "recipient_id": str(request.recipient_id),
            "source_associate_id": str(request.source_associate_id),
            "project_ids": sorted(str(value) for value in projects),
            "decision": "APPROVED",
            "reason": reason.strip(),
        },
    )
    return decision


def approval_service_grants_live_msr_access(*args, **kwargs):
    """No operational permission is activated by this service."""
    return False