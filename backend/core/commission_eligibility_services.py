from .models import Project, ProjectEvidence
from .payment_services import get_project_payment_status
from .documents import canonical_hash
from rest_framework.exceptions import ValidationError


def get_commission_eligibility(project_id):
    """
    Determine whether a project is eligible for commission calculation.

    This function does not create commissions.
    It only evaluates eligibility requirements.
    """

    project = (
        Project.objects
        .select_related('current_approved')
        .get(pk=project_id)
    )

    msr = project.current_approved

    if msr is None or msr.status != 'APPROVED':
        raise ValidationError(
            'Commission eligibility requires an approved MSR.'
        )

    payment_status = get_project_payment_status(
        project.id
    )

    if not payment_status['paid_in_full']:
        return {
            'eligible': False,
            'reason': 'Invoice is not fully paid after approved adjustments.',
            'payment_status': payment_status,
        }

    evidence = (
        ProjectEvidence.objects
        .filter(
            msr=msr,
            kind='WORK_COMPLETION',
        )
        .order_by(
            '-created_at',
            '-id',
        )
        .first()
    )

    if (
        evidence is None
        or evidence.data.get('verified') is not True
        or canonical_hash(evidence.data) != evidence.digest
    ):
        return {
            'eligible': False,
            'reason': 'Verified work completion evidence is required.',
            'payment_status': payment_status,
        }

    return {
        'eligible': True,
        'project_id': str(project.id),
        'msr_id': str(msr.id),
        'payment_status': payment_status,
        'completion_evidence_id': str(
            evidence.id
        ),
    }