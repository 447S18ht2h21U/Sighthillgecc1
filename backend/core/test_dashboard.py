from decimal import Decimal

from datetime import date

from django.test import TestCase

from .models import (
    Project,
    Customer,
    User,
    Role,
    InstallationSchedule,
)

from .dashboard_services import (
    get_project_dashboard_stage,
)

from .documents import generate

from . import tests as foundation

from .models import CustomerPayment

from .payment_services import verify_customer_payment

class DashboardTests(TestCase):

    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def test_project_defaults_to_completed_customer_record(self):

        stage = get_project_dashboard_stage(
            self.project,
        )

        self.assertEqual(
            stage,
            'completed_customer_record',
        )

    def test_contract_document_moves_project_to_contracted_for_work(self):

        approved = self.approve()

        generate(
            self.manager,
            approved.id,
            'CONTRACT',
        )

        stage = get_project_dashboard_stage(
            self.project,
        )

        self.assertEqual(
            stage,
            'contracted_for_work',
        )

    def test_invoice_document_moves_project_to_invoice_signed(self):

        approved = self.approve()

        generate(
            self.manager,
            approved.id,
            'INVOICE',
        )

        stage = get_project_dashboard_stage(
            self.project,
        )

        self.assertEqual(
            stage,
            'invoice_signed',
        )

    def test_installation_schedule_moves_project_to_installation_scheduled(self):

        schedule = InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            status=InstallationSchedule.Status.SCHEDULED,
            installation_manager=self.manager,
            scheduled_by=self.manager,
        )

        stage = get_project_dashboard_stage(
            self.project,
        )

        self.assertEqual(
            stage,
            'installation_scheduled',
        )

    def test_completion_certificate_moves_project_to_installation_complete(self):

        approved = self.approve()

        generate(
            self.manager,
            approved.id,
            'COMPLETION_NON_FINANCED',
        )

        stage = get_project_dashboard_stage(
            self.project,
        )

        self.assertEqual(
            stage,
            'installation_complete',
        )

    def test_verified_payment_moves_project_to_payment_received(self):

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

        verify_customer_payment(
            self.comptroller,
            payment.id,
        )

        stage = get_project_dashboard_stage(
            self.project,
        )

        self.assertEqual(
            stage,
            'payment_received',
        )