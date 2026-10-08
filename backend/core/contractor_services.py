"""GECC contractor onboarding and compensation services."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Role,
    ContractorEngagement,
    ContractorOnboardingDocument,
)
from .services import audit


REQUIRED_ONBOARDING_DOCUMENTS = frozenset({
    ContractorOnboardingDocument.Kind.W9,
    ContractorOnboardingDocument.Kind.LICENSE_FRONT,
    ContractorOnboardingDocument.Kind.LICENSE_BACK,
    ContractorOnboardingDocument.Kind.AGREEMENT,
})


def require_comptroller(actor):
    """Only an active Comptroller may finalize contractor onboarding."""
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or actor.role != Role.COMPTROLLER
    ):
        raise PermissionDenied(
            'An active Comptroller account is required.'
        )

@transaction.atomic
def approve_onboarding_document(actor, document_id):
    """Approve an onboarding document with an auditable transaction."""

    require_comptroller(actor)

    document = (
        ContractorOnboardingDocument.objects
        .select_for_update()
        .get(pk=document_id)
    )

    if document.status != ContractorOnboardingDocument.Status.PENDING:
        raise ValidationError(
            'Only pending onboarding documents may be approved.'
        )

    if not document.storage_reference.strip():
        raise ValidationError(
            'A stored document reference is required before approval.'
        )

    from django.utils import timezone

    document.status = ContractorOnboardingDocument.Status.APPROVED
    document.reviewed_by = actor
    document.reviewed_at = timezone.now()

    document.save(
        update_fields=['status', 'reviewed_by', 'reviewed_at']
    )

    audit(
        actor,
        'contractor.document.approved',
        document.id,
        {
            'engagement_id': str(document.engagement_id),
            'document_kind': document.kind,
        },
    )

    return document

@transaction.atomic
def activate_contractor_engagement(actor, engagement_id):
    """Activate an engagement only after required onboarding approvals."""

    require_comptroller(actor)

    engagement = (
        ContractorEngagement.objects
        .select_for_update()
        .get(pk=engagement_id)
    )

    if engagement.status != ContractorEngagement.Status.PENDING:
        raise ValidationError(
            'Only pending engagements may be activated.'
        )

    approved_kinds = set(
        ContractorOnboardingDocument.objects.filter(
            engagement=engagement,
            status=ContractorOnboardingDocument.Status.APPROVED,
            reviewed_by__is_active=True,
            reviewed_by__role=Role.COMPTROLLER,
            reviewed_at__isnull=False,
        ).values_list('kind', flat=True)
    )

    missing = REQUIRED_ONBOARDING_DOCUMENTS - approved_kinds

    if missing:
        raise ValidationError({
            'onboarding': 'Missing approved documents: '
            + ', '.join(sorted(missing))
        })

    engagement.status = ContractorEngagement.Status.ACTIVE
    engagement.save(update_fields=['status'])

    audit(
        actor,
        'contractor.engagement.activated',
        engagement.id,
        {
            'contractor_id': str(engagement.contractor_id),
            'engagement_code': engagement.engagement_code,
        },
    )

    return engagement

@transaction.atomic
def approve_compensation_plan(actor, plan_id):
    """Approve draft compensation terms through the Comptroller."""

    from django.utils import timezone
    from .models import ContractorCompensationPlan

    require_comptroller(actor)

    plan = (
        ContractorCompensationPlan.objects
        .select_for_update()
        .select_related('engagement')
        .get(pk=plan_id)
    )

    if plan.status != ContractorCompensationPlan.Status.DRAFT:
        raise ValidationError(
            'Only draft compensation plans may be approved.'
        )

    if plan.engagement.status != ContractorEngagement.Status.ACTIVE:
        raise ValidationError(
            'The contractor engagement must be active.'
        )

    if not plan.compensation_terms:
        raise ValidationError(
            'Compensation terms are required.'
        )

    plan.status = ContractorCompensationPlan.Status.APPROVED
    plan.approved_by = actor
    plan.approved_at = timezone.now()

    plan.save(
        update_fields=['status', 'approved_by', 'approved_at']
    )

    audit(
        actor,
        'contractor.compensation.approved',
        plan.id,
        {
            'engagement_id': str(plan.engagement_id),
            'version': plan.version,
        },
    )

    return plan
def get_effective_compensation_plan(engagement_id, as_of_date):
    """
    Return the approved compensation plan effective on a given date.

    Previously approved plans remain immutable.
    Draft and superseded plans are excluded.
    Returns None if no approved plan is effective.
    """
    from .models import ContractorCompensationPlan

    return (
        ContractorCompensationPlan.objects
        .filter(
            engagement_id=engagement_id,
            status=ContractorCompensationPlan.Status.APPROVED,
            effective_date__lte=as_of_date,
        )
        .order_by('-effective_date', '-version')
        .first()
    )
