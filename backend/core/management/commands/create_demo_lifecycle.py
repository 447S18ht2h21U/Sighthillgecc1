from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import User, Customer, Project, CustomerSignatureEvidence, InstallationSchedule, CustomerPayment, Role
from core.services import create_project, transition
from core.installation_schedule_services import complete_installation_schedule
from core import release
from core.documents import generate
from core.signing import prepare
from core.payment_services import verify_customer_payment


class Command(BaseCommand):
    help = 'Create the single VERIDIAN demo lifecycle project; development only.'

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != 'development' or not settings.DEBUG:
            raise CommandError('Development only.')

        try:
            sales = User.objects.get(username='sales')
            manager = User.objects.get(username='manager')
            comptroller = User.objects.get(username='comptroller')
        except User.DoesNotExist as exc:
            raise CommandError(
                'Run bootstrap_dev before creating the demo lifecycle.'
            ) from exc

        installer, _ = User.objects.get_or_create(
            username='installer',
            defaults={
                'email': 'installer@example.invalid',
                'role': Role.INSTALLATION_MANAGER,
                'initials': 'IM',
                'first_name': 'Demo',
                'last_name': 'Installer',
            },
        )

        customer, _ = Customer.objects.get_or_create(
            legal_name='VERIDIAN Demo Customer',
            defaults={
                'billing_address': '100 Demo Trail',
                'created_by': sales,
            },
        )

        project = Project.objects.filter(
            customer=customer,
            location='100 Demo Installation Way',
        ).first()

        if project is None:
            project = create_project(
                sales,
                customer,
                '100 Demo Installation Way',
                sales,
                manager,
            )

        if project.current_approved:
            msr = project.current_approved
        else:
            msr = project.pending

        if project.current_approved is None:
            snapshot = {
                **msr.snapshot,
                'contact': 'Demo Contact',
                'scope': 'VERIDIAN demo installation lifecycle',
                'equipment': [
                    {'description': 'Demo HVAC System', 'quantity': '1'}
                ],
                'materials': [
                    {'description': 'Demo Installation Materials', 'quantity': '1'}
                ],
                'base_price': '10000.00',
                'discount': '0.00',
                'tax': '0.00',
                'total_price': '10000.00',
                'payment_option': '50_PERCENT_DEPOSIT',
                'payment_terms': '50% deposit; balance at completion.',
                'financing_type': 'FINANCED',
            }

            msr = transition(
                sales,
                msr.id,
                'edit',
                msr.edit_sequence,
                snapshot=snapshot,
            )

            msr = transition(
                sales,
                msr.id,
                'submit',
                msr.edit_sequence,
            )

            msr = transition(
                manager,
                msr.id,
                'approve',
                msr.edit_sequence,
            )

        msr = project.current_approved

        CustomerSignatureEvidence.objects.get_or_create(
            msr=msr,
            document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
            signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
            digest='DEMO-CONTRACT-SIGNATURE',
            defaults={
                'signer_name': 'VERIDIAN Demo Customer',
                'signer_email': 'demo.customer@example.invalid',
                'signed_at': timezone.now(),
                'provider_reference': 'DEMO-CONTRACT',
            },
        )

        CustomerSignatureEvidence.objects.get_or_create(
            msr=msr,
            document_kind=CustomerSignatureEvidence.DocumentKind.INVOICE,
            signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
            digest='DEMO-INVOICE-SIGNATURE',
            defaults={
                'signer_name': 'VERIDIAN Demo Customer',
                'signer_email': 'demo.customer@example.invalid',
                'signed_at': timezone.now(),
                'provider_reference': 'DEMO-INVOICE',
            },
        )

        schedule, _ = InstallationSchedule.objects.get_or_create(
            project=project,
            defaults={
                'scheduled_date': timezone.localdate(),
                'installation_manager': installer,
                'scheduled_by': installer,
            },
        )

        if schedule.status == InstallationSchedule.Status.SCHEDULED:
            complete_installation_schedule(
                installer,
                schedule.id,
            )

        release.record_evidence(
            comptroller,
            msr.id,
            {
                'kind': 'WORK_COMPLETION',
                'verified': True,
                'source_reference': 'VERIDIAN DEMO COMPLETION',
                'verification_note': 'Demo lifecycle completion verification.',
                'completion_date': timezone.localdate().isoformat(),
                'work_verified': True,
                'permits_inspections_checked': True,
                'exceptions_resolved': True,
                'substitute_reason': 'Demo lifecycle verification.',
            },
        )

        generate(
            manager,
            msr.id,
            'COMPLETION_FINANCED',
        )

        plan, _ = prepare(
            manager,
            msr.id,
            {
                'group': 'COMPLETION_FINANCED',
                'customer_name': 'VERIDIAN Demo Customer',
                'customer_email': 'demo.customer@example.invalid',
                'gecc_signer': str(comptroller.id),
                'authority_note': 'Demo lifecycle completion authority review.',
                'substitute_reason': 'Installation Manager unavailable in demo scenario.',
            },
        )

        package, _ = release.prepare_package(
            comptroller,
            plan.id,
        )

        release.decide(
            manager,
            package.id,
            {
                'decision': 'APPROVED',
                'note': 'Demo lifecycle release reviewed and approved.',
                'documents_and_evidence_reviewed': True,
            },
        )

        payment = CustomerPayment.objects.filter(
            project=project,
            msr=msr,
            payment_reference='VERIDIAN-DEMO-DEPOSIT',
        ).first()

        if payment is None:
            payment = CustomerPayment.objects.create(
                project=project,
                msr=msr,
                kind=CustomerPayment.Kind.DEPOSIT,
                amount='5000.00',
                received_date=timezone.localdate(),
                payment_reference='VERIDIAN-DEMO-DEPOSIT',
                status=CustomerPayment.Status.PENDING,
                recorded_by=comptroller,
            )

        if payment.status != CustomerPayment.Status.VERIFIED:
            verify_customer_payment(
                comptroller,
                payment.id,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Demo project ready: {project.code}'
            )
        )
