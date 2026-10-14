"""Evidence-based project status dashboard."""

from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import (
    CustomerPayment,
    CustomerPaymentAdjustment,
    InstallationSchedule,
    ReleasePackage,
)
from .operational_visibility import operational_project_scope
from .payment_services import get_project_payment_status
from .services import validate_snapshot


DASHBOARD_STAGES = {
    'completed_customer_record': 'Completed Customer Record',
    'contracted_for_work': 'Contracted for Work',
    'invoice_signed': 'Invoice Signed',
    'installation_scheduled': 'Installation Scheduled',
    'installation_complete': 'Installation Complete',
    'payment_received': 'Payment Received',
}


def installation_completion_verified(project):
    """Return True only when installation completion has verified release evidence."""

    if not InstallationSchedule.objects.filter(
        project=project,
        status=InstallationSchedule.Status.COMPLETED,
    ).exists():
        return False

    evidence = project.current_approved.verification_evidence.filter(
        kind='WORK_COMPLETION',
    ).order_by('-created_at', '-id').first()

    if not evidence:
        return False

    if evidence.data.get('verified') is not True:
        return False

    package = ReleasePackage.objects.filter(
        plan__msr__project=project,
    ).order_by('-created_at', '-id').first()

    if not package:
        return False

    from . import release

    return release.status(package)['status'] == 'APPROVED'


def get_project_dashboard_stages(project):
    """Return independently verified stage memberships."""
    stages = []

    record = project.pending or project.current_approved

    if record is not None:
        try:
            validate_snapshot(record.snapshot, complete=True)
        except ValidationError:
            pass
        else:
            stages.append('completed_customer_record')

    # Generated documents and sandbox tests are not production
    # signature evidence. Signature stages remain unconfirmed.
    if InstallationSchedule.objects.filter(
        project=project,
        status=InstallationSchedule.Status.SCHEDULED,
    ).exists():
        stages.append('installation_scheduled')

    if installation_completion_verified(project):
        stages.append('installation_complete')

    if project.current_approved_id:
        try:
            payment = get_project_payment_status(project.id)
        except ValidationError:
            pass
        else:
            if payment['net_received'] > Decimal('0.00'):
                stages.append('payment_received')

    return stages


def get_project_dashboard_stage(project):
    """Compatibility interface; returns memberships, not one stage."""
    return get_project_dashboard_stages(project)


def get_project_payment_breakdown(project):
    """Return verified net receipts by payment type."""
    breakdown = {
        kind: Decimal('0.00')
        for kind in CustomerPayment.Kind.values
    }

    payments = CustomerPayment.objects.filter(
        project=project,
        status=CustomerPayment.Status.VERIFIED,
    ).prefetch_related('adjustments')

    for payment in payments:
        approved_adjustments = sum(
            (
                item.amount
                for item in payment.adjustments.all()
                if item.status == CustomerPaymentAdjustment.Status.APPROVED
            ),
            Decimal('0.00'),
        )
        breakdown[payment.kind] += payment.amount - approved_adjustments

    return breakdown


def get_dashboard_projects(actor):
    """Group visible projects by each independently earned stage."""
    dashboard = {key: [] for key in DASHBOARD_STAGES}

    projects = operational_project_scope(actor).select_related(
        'pending',
        'current_approved',
    )

    for project in projects:
        for stage in get_project_dashboard_stages(project):
            dashboard[stage].append(project)

    return dashboard

