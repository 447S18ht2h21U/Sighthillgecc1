"""Read-only database-backed eligibility inspection for MSR delegation.

This is NOT an access authorization function and is NOT registered in
the operational API. Live MSR permissions must continue to deny delegation
until the end-to-end policy and PostgreSQL controls are approved.
"""

from datetime import datetime
from uuid import UUID

from django.utils import timezone

from .models import Project, Role, User
from .msr_delegation_models import (
    MSRDelegationRequestProject,
    MSRDelegationTermination,
    MSRDelegationProjectInvalidation,
)
from .access_msr_delegation_effective_scope import (
    EffectiveScopeEvidence,
    evaluate_fixed_msr_scope,
)


def eligible_fixed_project_delegation(
    *, recipient_id, project_id, now=None,
):
    """Check durable evidence; fail closed on missing or changed facts."""
    if (
        type(recipient_id) is not UUID or not recipient_id.int
        or type(project_id) is not UUID or not project_id.int
    ):
        return False

    if now is None:
        now = timezone.now()
    if (
        not isinstance(now, datetime)
        or timezone.is_naive(now)
    ):
        return False

    recipient = User.objects.filter(
        pk=recipient_id,
        role=Role.SALES_ASSOCIATE,
        is_active=True,
    ).first()
    if recipient is None:
        return False

    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        return False

    scopes = MSRDelegationRequestProject.objects.filter(
        project_id=project_id,
        request__recipient_id=recipient_id,
        request__read_only=True,
        request__final_decision__result="APPROVED",
    ).select_related("request", "request__final_decision")

    for scope in scopes:
        request = scope.request
        decision = request.final_decision

        identities = (
            request.manager_id,
            request.recipient_id,
            request.source_associate_id,
            decision.decided_by_id,
        )
        if len(set(identities)) != 4:
            continue

        # Never use an invalidated or terminated delegation.
        terminated = MSRDelegationTermination.objects.filter(
            decision_id=decision.pk
        ).exists()
        invalidated = MSRDelegationProjectInvalidation.objects.filter(
            scope_id=scope.pk,
            decision_id=decision.pk,
        ).exists()
        if terminated or invalidated:
            continue

        evidence = EffectiveScopeEvidence(
            request_id=request.pk,
            recipient_id=request.recipient_id,
            project_id=scope.project_id,
            original_owner_id=request.source_associate_id,
            captured_revision=scope.owner_revision,
            decision_request_id=decision.request_id,
            decision_result=decision.result,
            begins_at=request.starts_at,
            ends_at=request.ends_at,
            terminated=terminated,
            project_invalidated=invalidated,
        )
        if evaluate_fixed_msr_scope(
            evidence,
            recipient_id=recipient_id,
            project_id=project_id,
            current_owner_id=project.sales_associate_id,
            current_revision=project.ownership_revision,
            now=now,
            recipient_active=recipient.is_active,
        ):
            return True

    return False


def eligibility_check_grants_live_msr_access(*args, **kwargs):
    """No caller may activate operational delegation via this module."""
    return False