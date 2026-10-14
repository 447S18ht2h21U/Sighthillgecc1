from django.test import TestCase
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    Customer,
    Project,
    User,
    Role,
    CustomerSignatureEvidence,
)

from .services import create_project
from .installation_eligibility import ensure_installation_eligible


class InstallationEligibilityTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username='eligibility_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CP',
        )

        self.sales = User.objects.create_user(
            username='eligibility_sales',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.sales_manager = User.objects.create_user(
            username='eligibility_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.customer = Customer.objects.create(
            legal_name='Eligibility Test Customer',
            billing_address='123 Eligibility Road',
            created_by=self.sales,
        )

        self.project = create_project(
            self.sales,
            self.customer,
            'Eligibility Test Location',
            self.sales,
            self.sales_manager,
        )

    def prepare_installation_state(
        self,
        contract=True,
        invoice=True,
        cancellation=True,
        deposit=True,
        financed=True,
        signed_days_ago=10,
    ):
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
            'payment_terms': '50% deposit when eligible; balance upon completion.' if financed else '100% due upon completion.',
            'base_price': '10000.00',
            'discount': '0.00',
            'tax': '0.00',
            'total_price': '10000.00',
            'financing_type': 'FINANCED' if financed else 'NON_FINANCED',
            'payment_option': '50_PERCENT_DEPOSIT' if financed else '100_PERCENT_COMPLETION',
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

        signed_at = timezone.now() - timedelta(days=signed_days_ago)

        if contract:
            CustomerSignatureEvidence.objects.create(
                msr=msr,
                document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
                signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
                signer_name='Test Customer',
                signer_email='customer@example.com',
                signed_at=signed_at,
                provider_reference='TEST-CONTRACT',
                digest='TEST-CONTRACT-DIGEST',
            )

        if invoice:
            CustomerSignatureEvidence.objects.create(
                msr=msr,
                document_kind=CustomerSignatureEvidence.DocumentKind.INVOICE,
                signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
                signer_name='Test Customer',
                signer_email='customer@example.com',
                signed_at=signed_at,
                provider_reference='TEST-INVOICE',
                digest='TEST-INVOICE-DIGEST',
            )

        if cancellation:
            ProjectEvidence.objects.create(
                msr=msr,
                kind='CANCELLATION_DEADLINE',
                created_by=self.comptroller,
                data={
                    'verified': True,
                    'deadline': (
                        signed_at + timedelta(days=1)
                    ).isoformat(),
                },
                digest='TEST-CANCELLATION-DIGEST',
            )

        if financed and deposit:
            payment = CustomerPayment.objects.create(
                project=self.project,
                msr=msr,
                kind=CustomerPayment.Kind.DEPOSIT,
                amount='5000.00',
                received_date=timezone.localdate(),
                payment_reference='TEST-DEPOSIT',
                status=CustomerPayment.Status.PENDING,
                recorded_by=self.comptroller,
            )

            verify_customer_payment(
                self.comptroller,
                payment.id,
            )

        return msr

        self.comptroller = User.objects.create_user(
            username='eligibility_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CP',
        )

        self.sales = User.objects.create_user(
            username='eligibility_sales',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.sales_manager = User.objects.create_user(
            username='eligibility_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.customer = Customer.objects.create(
            legal_name='Eligibility Test Customer',
            billing_address='123 Eligibility Road',
            created_by=self.sales,
        )

        self.project = create_project(
            self.sales,
            self.customer,
            'Eligibility Test Location',
            self.sales,
            self.sales_manager,
        )

    def test_missing_contract_signature_blocks_installation(self):
        self.prepare_installation_state(contract=False)

        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)


    def test_missing_invoice_signature_blocks_installation(self):
        self.prepare_installation_state(invoice=False)

        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)


    def test_missing_cancellation_evidence_blocks_installation(self):
        self.prepare_installation_state(cancellation=False)

        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)


    def test_financed_project_requires_verified_deposit(self):
        self.prepare_installation_state(
            financed=True,
            deposit=False,
        )

        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)


    def test_non_financed_project_does_not_require_deposit(self):
        self.prepare_installation_state(
            financed=False,
            deposit=False,
        )

        self.assertTrue(
            ensure_installation_eligible(self.project)
        )


    def test_waiting_period_blocks_early_installation(self):
        self.prepare_installation_state(
            signed_days_ago=1,
        )

        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)


