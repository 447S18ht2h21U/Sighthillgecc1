from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from . import tests as foundation
from .dashboard_services import get_project_dashboard_stages
from .documents import generate
from .models import CustomerPayment, InstallationSchedule, ProjectEvidence
from .payment_services import verify_customer_payment
from . import release, test_signing as signing_tests
from .signing import prepare


@override_settings(DEBUG=True)
class DashboardTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def stages(self):
        self.project.refresh_from_db()
        return get_project_dashboard_stages(self.project)

    def test_incomplete_project_does_not_qualify_as_completed_record(self):
        self.assertNotIn('completed_customer_record', self.stages())

    def test_complete_approved_record_qualifies(self):
        self.approve()
        self.assertIn('completed_customer_record', self.stages())

    def test_generated_contract_is_not_signed_evidence(self):
        approved = self.approve()
        generate(self.manager, approved.id, 'CONTRACT')
        self.assertNotIn('contracted_for_work', self.stages())

    def test_generated_invoice_is_not_signed_evidence(self):
        approved = self.approve()
        generate(self.manager, approved.id, 'INVOICE')
        self.assertNotIn('invoice_signed', self.stages())

    def test_scheduled_installation_qualifies_independently(self):
        InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            status=InstallationSchedule.Status.SCHEDULED,
            installation_manager=self.manager,
            scheduled_by=self.manager,
        )
        self.assertIn('installation_scheduled', self.stages())
        self.assertNotIn('completed_customer_record', self.stages())

    def test_generated_completion_certificate_is_not_signed_evidence(self):
        approved = self.approve()
        generate(self.manager, approved.id, 'COMPLETION_NON_FINANCED')
        self.assertNotIn('installation_complete', self.stages())

    def test_verified_deposit_qualifies_without_hiding_other_stages(self):
        approved = self.approve()
        payment = CustomerPayment.objects.create(
            project=self.project,
            msr=approved,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='DASH-TEST-001',
            recorded_by=self.sales,
        )
        verify_customer_payment(self.comptroller, payment.id)

        InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            status=InstallationSchedule.Status.SCHEDULED,
            installation_manager=self.manager,
            scheduled_by=self.manager,
        )

        stages = self.stages()
        self.assertIn('completed_customer_record', stages)
        self.assertIn('installation_scheduled', stages)
        self.assertIn('payment_received', stages)
        self.assertNotIn('contracted_for_work', stages)
        self.assertNotIn('invoice_signed', stages)
        self.assertNotIn('installation_complete', stages)

    def test_verified_completion_release_qualifies_as_installation_complete(self):
        approved = self.approve()

        InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            status=InstallationSchedule.Status.COMPLETED,
            installation_manager=self.manager,
            scheduled_by=self.manager,
        )

        self.manager.first_name = 'Review'
        self.manager.last_name = 'Manager'
        self.manager.email = 'manager@example.invalid'
        self.manager.save()

        self.comptroller.first_name = 'Review'
        self.comptroller.last_name = 'Comptroller'
        self.comptroller.email = 'comptroller@example.invalid'
        self.comptroller.save()

        data = {
            'group': 'COMPLETION_NON_FINANCED',
            'customer_name': 'Authorized Customer',
            'customer_email': 'customer@example.invalid',
            'gecc_signer': str(self.comptroller.id),
            'authority_note': 'Synthetic test identity and signing authority reviewed.',
            'substitute_reason': 'Synthetic test scenario',
        }

        for kind in ['CONTRACT', 'INVOICE', 'COMPLETION_NON_FINANCED']:
            generate(self.manager, approved.id, kind)

        plan, _ = prepare(
            self.manager,
            approved.id,
            data,
        )

        release.record_evidence(
            self.comptroller,
            approved.id,
            {
                'kind': 'WORK_COMPLETION',
                'verified': True,
                'source_reference': 'TEST-COMPLETION',
                'verification_note': 'Synthetic completion verification.',
                'completion_date': '2026-10-08',
                'work_verified': True,
                'permits_inspections_checked': True,
                'exceptions_resolved': True,
                'substitute_reason': 'Synthetic test scenario',
            },
        )

        package, _ = release.prepare_package(
            self.comptroller,
            plan.id,
        )

        release.decide(
            self.manager,
            package.id,
            {
                'decision': 'APPROVED',
                'note': 'Reviewed completion documents and evidence.',
                'documents_and_evidence_reviewed': True,
            },
        )

        self.assertIn(
            'installation_complete',
            self.stages(),
        )

