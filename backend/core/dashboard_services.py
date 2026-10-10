from .models import (
    Document,
    InstallationSchedule,
    CustomerPayment,
    Project,
)


DASHBOARD_STAGES = {
    'completed_customer_record': 'Completed Customer Record',
    'contracted_for_work': 'Contracted for Work',
    'invoice_signed': 'Invoice Signed',
    'installation_scheduled': 'Installation Scheduled',
    'installation_complete': 'Installation Complete',
    'payment_received': 'Payment Received',
}

def get_project_dashboard_stage(project):

    if CustomerPayment.objects.filter(
        project=project,
        status=CustomerPayment.Status.VERIFIED,
    ).exists():
        return 'payment_received'

    if project.versions.filter(
        status='APPROVED',
        documents__kind__in=[
            Document.Kind.COMPLETION_FINANCED,
            Document.Kind.COMPLETION_NON_FINANCED,
        ],
    ).exists():
        return 'installation_complete'

    if InstallationSchedule.objects.filter(
        project=project,
        status=InstallationSchedule.Status.SCHEDULED,
    ).exists():
        return 'installation_scheduled'

    if project.versions.filter(
        status='APPROVED',
        documents__kind=Document.Kind.INVOICE,
    ).exists():
        return 'invoice_signed'

    if project.versions.filter(
        status='APPROVED',
        documents__kind=Document.Kind.CONTRACT,
    ).exists():
        return 'contracted_for_work'

    return 'completed_customer_record'
