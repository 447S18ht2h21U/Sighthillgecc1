from django.test import TestCase
from rest_framework.test import APIClient

from . import tests as foundation
from .dashboard_services import DASHBOARD_STAGES


class DashboardAPITests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def test_technical_associate_sees_only_assigned_projects(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from .models import (
            InstallationSchedule, Project, ProjectTechnicalAssignment, Role
        )

        User = get_user_model()
        technician = User.objects.create_user(
            username='dashboard_test_technician',
            password='temporary-test-only',
            role=Role.TECHNICIAN,
        )

        other_project = Project.objects.create(
            customer=self.project.customer,
            location='Unassigned technical dashboard project',
            sales_associate=self.sales,
            reviewer=self.manager,
        )

        for project in (self.project, other_project):
            InstallationSchedule.objects.create(
                project=project,
                scheduled_date=timezone.localdate(),
                status=InstallationSchedule.Status.SCHEDULED,
                installation_manager=self.manager,
                scheduled_by=self.manager,
            )

        ProjectTechnicalAssignment.objects.create(
            project=self.project,
            technical_associate=technician,
            assigned_by=self.manager,
            status=ProjectTechnicalAssignment.Status.ACTIVE,
            effective_date=timezone.localdate(),
        )

        client = APIClient()
        client.force_authenticate(technician)
        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)

        scheduled = next(
            stage for stage in response.data['stages']
            if stage['key'] == 'installation_scheduled'
        )
        visible_ids = {str(item['id']) for item in scheduled['projects']}

        self.assertEqual(visible_ids, {str(self.project.id)})
        self.assertNotIn(str(other_project.id), visible_ids)

    def test_sales_associate_sees_only_assigned_projects(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from .models import InstallationSchedule, Project, Role

        User = get_user_model()
        other_sales = User.objects.create_user(
            username='dashboard_unassigned_sales',
            password='temporary-test-only',
            role=Role.SALES_ASSOCIATE,
        )
        other_project = Project.objects.create(
            customer=self.project.customer,
            location='Unassigned dashboard test location',
            sales_associate=other_sales,
            reviewer=self.manager,
        )

        for project in (self.project, other_project):
            InstallationSchedule.objects.create(
                project=project,
                scheduled_date=timezone.localdate(),
                status=InstallationSchedule.Status.SCHEDULED,
                installation_manager=self.manager,
                scheduled_by=self.manager,
            )

        client = APIClient()
        client.force_authenticate(self.sales)
        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)

        scheduled = next(
            stage for stage in response.data['stages']
            if stage['key'] == 'installation_scheduled'
        )
        visible_ids = {str(item['id']) for item in scheduled['projects']}

        self.assertEqual(visible_ids, {str(self.project.id)})
        self.assertNotIn(str(other_project.id), visible_ids)

    def test_manager_can_see_all_scheduled_projects(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from .models import InstallationSchedule, Project, Role

        User = get_user_model()
        other_sales = User.objects.create_user(
            username='dashboard_other_sales',
            password='temporary-test-only',
            role=Role.SALES_ASSOCIATE,
        )
        other_project = Project.objects.create(
            customer=self.project.customer,
            location='Dashboard test location',
            sales_associate=other_sales,
            reviewer=self.manager,
        )

        for project in (self.project, other_project):
            InstallationSchedule.objects.create(
                project=project,
                scheduled_date=timezone.localdate(),
                status=InstallationSchedule.Status.SCHEDULED,
                installation_manager=self.manager,
                scheduled_by=self.manager,
            )

        client = APIClient()
        client.force_authenticate(self.manager)
        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)
        scheduled = next(
            stage for stage in response.data['stages']
            if stage['key'] == 'installation_scheduled'
        )
        visible_ids = {item['id'] for item in scheduled['projects']}
        self.assertEqual(visible_ids, {str(self.project.id), str(other_project.id)})

    def test_dashboard_rejects_post_requests(self):
        client = APIClient()
        client.force_authenticate(self.sales)

        response = client.post('/api/project-dashboard/', {}, format='json')

        self.assertEqual(response.status_code, 405)

    def test_unauthenticated_access_denied(self):
        client = APIClient()

        response = client.get('/api/project-dashboard/')

        self.assertIn(response.status_code, (401, 403))

    def test_six_stages_and_no_unearned_milestones(self):
        client = APIClient()
        client.force_authenticate(self.sales)

        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)

        stages = response.data['stages']

        self.assertEqual(len(stages), 6)
        self.assertEqual(
            [(stage['key'], stage['name']) for stage in stages],
            list(DASHBOARD_STAGES.items()),
        )

        for stage in stages:
            self.assertEqual(stage['count'], 0)
            self.assertEqual(stage['projects'], [])

        self.assertIn('no-store', response['Cache-Control'])


    def test_payment_breakdown_excludes_pending_receipts(self):
        from datetime import date
        from decimal import Decimal

        from .models import CustomerPayment
        from .payment_services import verify_customer_payment

        approved = self.approve()

        deposit = CustomerPayment.objects.create(
            project=self.project,
            msr=approved,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='DASH-API-DEPOSIT-001',
            recorded_by=self.sales,
        )
        verify_customer_payment(self.comptroller, deposit.id)

        CustomerPayment.objects.create(
            project=self.project,
            msr=approved,
            kind=CustomerPayment.Kind.FINAL,
            amount=Decimal('200.00'),
            received_date=date(2026, 10, 8),
            payment_reference='DASH-API-PENDING-001',
            recorded_by=self.sales,
        )

        client = APIClient()
        client.force_authenticate(self.sales)
        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)

        stages = {
            stage['key']: stage
            for stage in response.data['stages']
        }

        received = stages['payment_received']
        self.assertEqual(received['count'], 1)
        self.assertEqual(
            received['projects'][0]['payments'],
            {
                'deposit': '500.00',
                'final': '0.00',
                'full': '0.00',
            },
        )
        self.assertEqual(
            stages['completed_customer_record']['count'],
            1,
        )


    def test_payment_breakdown_deducts_only_approved_refunds(self):
        from datetime import date
        from decimal import Decimal

        from .models import CustomerPayment, CustomerPaymentAdjustment
        from .payment_services import (
            approve_customer_payment_adjustment,
            verify_customer_payment,
        )

        approved = self.approve()

        payment = CustomerPayment.objects.create(
            project=self.project,
            msr=approved,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount=Decimal('500.00'),
            received_date=date(2026, 10, 8),
            payment_reference='DASH-REFUND-PAYMENT-001',
            recorded_by=self.sales,
        )
        verify_customer_payment(self.comptroller, payment.id)

        refund = CustomerPaymentAdjustment.objects.create(
            payment=payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal('200.00'),
            adjustment_date=date(2026, 10, 8),
            adjustment_reference='DASH-REFUND-APPROVED-001',
            reason='Dashboard approved refund test',
            recorded_by=self.sales,
        )
        approve_customer_payment_adjustment(
            self.comptroller,
            refund.id,
        )

        CustomerPaymentAdjustment.objects.create(
            payment=payment,
            kind=CustomerPaymentAdjustment.Kind.REFUND,
            amount=Decimal('50.00'),
            adjustment_date=date(2026, 10, 8),
            adjustment_reference='DASH-REFUND-PENDING-001',
            reason='Dashboard pending refund test',
            recorded_by=self.sales,
        )

        client = APIClient()
        client.force_authenticate(self.sales)
        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)

        received = next(
            stage for stage in response.data['stages']
            if stage['key'] == 'payment_received'
        )

        self.assertEqual(received['count'], 1)
        self.assertEqual(
            received['projects'][0]['payments'],
            {
                'deposit': '300.00',
                'final': '0.00',
                'full': '0.00',
            },
        )


    def test_payment_breakdown_reports_all_three_categories(self):
        from datetime import date
        from decimal import Decimal

        from .models import CustomerPayment
        from .payment_services import verify_customer_payment

        approved = self.approve()

        cases = (
            (CustomerPayment.Kind.DEPOSIT, '200.00', 'DEPOSIT'),
            (CustomerPayment.Kind.FINAL, '300.00', 'FINAL'),
            (CustomerPayment.Kind.FULL, '500.00', 'FULL'),
        )

        for kind, amount, reference in cases:
            payment = CustomerPayment.objects.create(
                project=self.project,
                msr=approved,
                kind=kind,
                amount=Decimal(amount),
                received_date=date(2026, 10, 8),
                payment_reference='DASH-CATEGORY-' + reference,
                recorded_by=self.sales,
            )
            verify_customer_payment(self.comptroller, payment.id)

        client = APIClient()
        client.force_authenticate(self.sales)
        response = client.get('/api/project-dashboard/')

        self.assertEqual(response.status_code, 200)

        received = next(
            stage for stage in response.data['stages']
            if stage['key'] == 'payment_received'
        )

        self.assertEqual(received['count'], 1)
        self.assertEqual(
            received['projects'][0]['payments'],
            {
                'deposit': '200.00',
                'final': '300.00',
                'full': '500.00',
            },
        )
