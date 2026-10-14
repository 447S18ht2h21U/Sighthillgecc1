from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Customer,
    User,
    Role,
)

from .services import create_project


class InstallationReadinessAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.sales = User.objects.create_user(
            username="readiness_sales",
            password="test-password",
            role=Role.SALES_ASSOCIATE,
            initials="RS",
        )

        self.sales_manager = User.objects.create_user(
            username="readiness_manager",
            password="test-password",
            role=Role.SALES_MANAGER,
            initials="RM",
        )

        self.installation_manager = User.objects.create_user(
            username="readiness_installation",
            password="test-password",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )

        self.comptroller = User.objects.create_user(
            username="readiness_comptroller",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="CP",
        )

        self.customer = Customer.objects.create(
            legal_name="Readiness Test Customer",
            billing_address="123 Readiness Road",
            created_by=self.sales,
        )

        self.project = create_project(
            self.sales,
            self.customer,
            "Readiness Test Location",
            self.sales,
            self.sales_manager,
        )

    def prepare_ready_project(self):
        from datetime import timedelta
        from django.utils import timezone
        from .services import transition
        from .models import (
            CustomerSignatureEvidence,
            ProjectEvidence,
            CustomerPayment,
        )
        from .payment_services import verify_customer_payment

        self.project.refresh_from_db()

        msr = self.project.pending

        msr.snapshot.update({
            'scope': 'Install HVAC equipment',
            'payment_terms': '50% deposit when eligible; balance upon completion.',
            'base_price': '10000.00',
            'discount': '0.00',
            'tax': '0.00',
            'total_price': '10000.00',
            'financing_type': 'FINANCED',
            'payment_option': '50_PERCENT_DEPOSIT',
        })

        msr = transition(
            self.sales,
            msr.id,
            'edit',
            msr.edit_sequence,
            snapshot=msr.snapshot,
        )

        msr = transition(
            self.sales,
            msr.id,
            'submit',
            msr.edit_sequence,
        )

        msr = transition(
            self.sales_manager,
            msr.id,
            'approve',
            msr.edit_sequence,
        )

        self.project.refresh_from_db()
        msr = self.project.current_approved

        signed_at = timezone.now() - timedelta(days=10)

        CustomerSignatureEvidence.objects.create(
            msr=msr,
            document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
            signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
            signer_name='Test Customer',
            signer_email='customer@example.com',
            signed_at=signed_at,
            provider_reference='TEST-CONTRACT',
            digest='READINESS-CONTRACT',
        )

        CustomerSignatureEvidence.objects.create(
            msr=msr,
            document_kind=CustomerSignatureEvidence.DocumentKind.INVOICE,
            signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
            signer_name='Test Customer',
            signer_email='customer@example.com',
            signed_at=signed_at,
            provider_reference='TEST-INVOICE',
            digest='READINESS-INVOICE',
        )

        ProjectEvidence.objects.create(
            msr=msr,
            kind='CANCELLATION_DEADLINE',
            created_by=self.sales_manager,
            data={
                'verified': True,
                'deadline': (
                    signed_at + timedelta(days=1)
                ).isoformat(),
            },
            digest='READINESS-CANCELLATION',
        )

        payment = CustomerPayment.objects.create(
            project=self.project,
            msr=msr,
            kind=CustomerPayment.Kind.DEPOSIT,
            amount='5000.00',
            received_date=timezone.localdate(),
            payment_reference='READINESS-DEPOSIT',
            status=CustomerPayment.Status.PENDING,
            recorded_by=self.comptroller,
        )

        verify_customer_payment(
            self.comptroller,
            payment.id,
        )

    def test_installation_manager_can_view_project_readiness(self):
        self.prepare_ready_project()

        self.client.force_authenticate(
            self.installation_manager
        )

        response = self.client.get(
            f"/api/operational-projects/{self.project.pk}/installation-eligibility/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.data["eligible"]
        )


    def test_sales_associate_can_view_assigned_project_readiness(self):
        self.prepare_ready_project()

        self.client.force_authenticate(
            self.sales
        )

        response = self.client.get(
            f"/api/operational-projects/{self.project.pk}/installation-eligibility/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )


    def test_unrelated_sales_associate_cannot_view_project_readiness(self):
        other_sales = User.objects.create_user(
            username="other_readiness_sales",
            password="test-password",
            role=Role.SALES_ASSOCIATE,
            initials="OR",
        )

        self.prepare_ready_project()

        self.client.force_authenticate(
            other_sales
        )

        response = self.client.get(
            f"/api/operational-projects/{self.project.pk}/installation-eligibility/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )


    def test_readiness_response_contains_requirements(self):
        self.prepare_ready_project()

        self.client.force_authenticate(
            self.installation_manager
        )

        response = self.client.get(
            f"/api/operational-projects/{self.project.pk}/installation-eligibility/"
        )

        self.assertIn(
            "requirements",
            response.data,
        )

        self.assertIn(
            "blocking_reasons",
            response.data,
        )

    def test_ready_project_reports_all_requirements_complete(self):
        self.prepare_ready_project()

        self.client.force_authenticate(
            self.installation_manager
        )

        response = self.client.get(
            f"/api/operational-projects/{self.project.pk}/installation-eligibility/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.data["eligible"]
        )

        self.assertFalse(
            response.data["blocking_reasons"]
        )

        self.assertTrue(
            all(response.data["requirements"].values())
        )

