from decimal import Decimal
from datetime import date

from django.test import TestCase

from .commission_eligibility_services import (
    get_commission_eligibility,
)
from .documents import canonical_hash
from .models import (
    Customer,
    Project,
    MSR,
    CustomerPayment,
    ProjectCostRecord,
    ProjectEvidence,
    Role,
    User,
)
from .payment_services import verify_customer_payment
from .project_cost_services import approve_project_cost_record


class CommissionEligibilityTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username='eligibility_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.sales_manager = User.objects.create_user(
            username='eligibility_sales_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_associate = User.objects.create_user(
            username='eligibility_sales_associate',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.customer = Customer.objects.create(
            legal_name='Eligibility Test Customer',
            billing_address='123 Eligibility Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='ELIGIBILITY-001',
            customer=self.customer,
            location='Eligibility location',
            sales_associate=self.sales_associate,
            reviewer=self.sales_manager,
            state='APPROVED',
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '10000.00',
            },
            created_by=self.sales_associate,
            prepared_by=self.sales_associate,
            approved_by=self.comptroller,
        )

        self.project.current_approved = self.msr
        self.project.save(
            update_fields=['current_approved']
        )

        self.cost_record = ProjectCostRecord.objects.create(
            project=self.project,
            msr=self.msr,
            version=1,
            equipment_cost=Decimal('2000.00'),
            material_cost=Decimal('1000.00'),
            dealer_fee=Decimal('500.00'),
            technician_cost=Decimal('750.00'),
            lead_cost=Decimal('3000.00'),
            damon_cost=Decimal('500.00'),
            jerry_cost=Decimal('250.00'),
            created_by=self.sales_manager,
        )

        approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

        self.payment = CustomerPayment.objects.create(
            project=self.project,
            msr=self.msr,
            kind=CustomerPayment.Kind.FULL,
            amount=Decimal('10000.00'),
            received_date=date(2026, 10, 8),
            payment_reference='ELIGIBILITY-PAYMENT-001',
            recorded_by=self.sales_manager,
        )

        verify_customer_payment(
            self.comptroller,
            self.payment.id,
        )

    def test_paid_completed_project_is_commission_eligible(self):
        evidence_data = {
            'source_reference': 'WORK-COMPLETE-001',
            'verification_note': 'Installation completed and verified.',
            'snapshot_sha256': canonical_hash(
                self.msr.snapshot
            ),
            'method': 'MANUAL_ATTESTATION',
            'verified': True,
            'completion_date': '2026-10-08',
            'work_verified': True,
            'permits_inspections_checked': True,
            'exceptions_resolved': True,
        }

        evidence = ProjectEvidence.objects.create(
            msr=self.msr,
            kind='WORK_COMPLETION',
            created_by=self.comptroller,
            data=evidence_data,
            digest=canonical_hash(evidence_data),
        )

        result = get_commission_eligibility(
            self.project.id
        )

        self.assertTrue(
            result['eligible']
        )

        self.assertEqual(
            result['completion_evidence_id'],
            str(evidence.id),
        )

    def test_unpaid_project_is_not_commission_eligible(self):
        unpaid_project = Project.objects.create(
            code='ELIGIBILITY-UNPAID-001',
            customer=self.customer,
            location='Unpaid location',
            sales_associate=self.sales_associate,
            reviewer=self.sales_manager,
            state='APPROVED',
        )

        unpaid_msr = MSR.objects.create(
            project=unpaid_project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '10000.00',
            },
            created_by=self.sales_associate,
            prepared_by=self.sales_associate,
            approved_by=self.comptroller,
        )

        unpaid_project.current_approved = unpaid_msr
        unpaid_project.save(
            update_fields=['current_approved']
        )

        result = get_commission_eligibility(
            unpaid_project.id
        )

        self.assertFalse(
            result['eligible']
        )

        self.assertEqual(
            result['reason'],
            'Invoice is not fully paid after approved adjustments.',
        )

    def test_paid_project_without_completion_evidence_is_not_eligible(self):
        result = get_commission_eligibility(
            self.project.id
        )

        self.assertFalse(
            result['eligible']
        )

        self.assertEqual(
            result['reason'],
            'Verified work completion evidence is required.',
        )

    def test_tampered_completion_evidence_is_not_eligible(self):
        evidence_data = {
            'source_reference': 'WORK-COMPLETE-TAMPER-001',
            'verification_note': 'Installation completed and verified.',
            'snapshot_sha256': canonical_hash(
                self.msr.snapshot
            ),
            'method': 'MANUAL_ATTESTATION',
            'verified': True,
            'completion_date': '2026-10-08',
            'work_verified': True,
            'permits_inspections_checked': True,
            'exceptions_resolved': True,
        }

        ProjectEvidence.objects.create(
            msr=self.msr,
            kind='WORK_COMPLETION',
            created_by=self.comptroller,
            data=evidence_data,
            digest='invalid-digest',
        )

        result = get_commission_eligibility(
            self.project.id
        )

        self.assertFalse(
            result['eligible']
        )

        self.assertEqual(
            result['reason'],
            'Verified work completion evidence is required.',
        )
