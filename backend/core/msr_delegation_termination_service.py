"""Transactional termination evidence for fixed-project MSR delegation.

No operational MSR visibility or URL is registered by this module.
Records are appended; decisions and historical evidence are never edited.
"""

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Role, User
from .msr_delegation_models import (
    MSRDelegationDecision,
    MSRDelegationRequest,
    MSRDelegationTermination,
)
from .services import audit


def _valid_id(value):
    return type(value) is UUID and value.int != 0


@transaction.atomic
def terminate_fixed_msr_delegation(
    *, decision_id, actor_id, kind, reason,
):
    """Append one authorized termination and its audit atomically."""
    allowed = (
        MSRDelegationTermination.Kind.SURRENDER,
        MSRDelegationTermination.Kind.REVOCATION,
    )
    if (
        not _valid_id(decision_id)
        or not _valid_id(actor_id)
        or kind not in allowed
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2000
    ):
        raise PermissionDenied("Invalid termination request.")

    reference = MSRDelegationDecision.objects.filter(
        pk=decision_id
    ).values_list("request_id", flat=True).first()
    if reference is None:
        raise PermissionDenied("Delegation decision does not exist.")

    # Decision/request locks serialize termination against another
    # termination. Database one-to-one uniqueness is the final barrier.
    request = MSRDelegationRequest.objects.select_for_update().get(pk=reference)
    decision = MSRDelegationDecision.objects.select_for_update().get(
        pk=decision_id,
        request_id=request.pk,
    )
    if decision.result != MSRDelegationDecision.Result.APPROVED:
        raise PermissionDenied("Only approved delegations can be terminated.")

    if MSRDelegationTermination.objects.filter(
        decision_id=decision.pk
    ).exists():
        raise PermissionDenied("Delegation is already terminated.")

    actor = User.objects.select_for_update().filter(pk=actor_id).first()
    if actor is None or not actor.is_active:
        raise PermissionDenied("Inactive or unknown actor.")

    if kind == MSRDelegationTermination.Kind.SURRENDER:
        if (
            actor.pk != request.recipient_id
            or actor.role != Role.SALES_ASSOCIATE
        ):
            raise PermissionDenied("Only the recipient may surrender access.")
        authority = "RECIPIENT_VOLUNTARY_SURRENDER"
    else:
        if (
            actor.role not in (Role.CEO, Role.COMPTROLLER)
            or actor.pk in (
                request.manager_id,
                request.recipient_id,
                request.source_associate_id,
            )
        ):
            raise PermissionDenied("Independent executive authority required.")
        authority = "INDEPENDENT_CEO_OR_COMPTROLLER"

    terminated_at = timezone.now()
    termination = MSRDelegationTermination.objects.create(
        decision=decision,
        terminated_by=actor,
        kind=kind,
        terminated_at=terminated_at,
        reason=reason.strip(),
        authority_reference=authority,
    )
    audit(
        actor,
        "msr.delegation.terminated",
        termination.pk,
        {
            "request_id": str(request.pk),
            "decision_id": str(decision.pk),
            "kind": kind,
            "reason": reason.strip(),
            "authority_reference": authority,
            "terminated_at": terminated_at.isoformat(),
        },
    )
    return termination


def termination_service_grants_live_msr_access(*args, **kwargs):
    return False