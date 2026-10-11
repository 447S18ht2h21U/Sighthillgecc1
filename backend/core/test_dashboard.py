from datetime import date
from decimal import Decimal

from django.test import TestCase

from . import tests as foundation
from .dashboard_services import get_project_dashboard_stages
from .documents import generate
from .models import CustomerPayment, InstallationSchedule
from .payment_services import verify_customer_payment


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
