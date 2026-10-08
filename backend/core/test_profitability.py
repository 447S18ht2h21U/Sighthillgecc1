from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .models import (
    Customer,
    Project,
    MSR,
    ProjectCostRecord,
    Role,
    User,
)
from .project_cost_services import approve_project_cost_record
from .profitability_services import calculate_gross_profit


class ProfitabilityTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username='profit_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='PC',
        )

        self.sales_manager = User.objects.create_user(
            username='profit_sales_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_associate = User.objects.create_user(
            username='profit_sales_associate',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.customer = Customer.objects.create(
            legal_name='Profit Test Customer',
            billing_address='123 Profit Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='PROFIT-TEST-001',
            customer=self.customer,
            location='Profit test location',
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

    def test_calculates_gross_profit_from_approved_records(self):
        result = calculate_gross_profit(
            self.project.id
        )

        self.assertEqual(
            result['invoice_amount'],
            Decimal('10000.00'),
        )

        self.assertEqual(
            result['total_cost'],
            Decimal('8000.00'),
        )

        self.assertEqual(
            result['gross_profit'],
            Decimal('2000.00'),
        )

        self.assertEqual(
            result['cost_record_id'],
            str(self.cost_record.id),
        )

    def test_missing_approved_cost_record_is_rejected(self):
        project = Project.objects.create(
            code='PROFIT-NO-COST-001',
            customer=self.customer,
            location='No cost location',
            sales_associate=self.sales_associate,
            reviewer=self.sales_manager,
            state='APPROVED',
        )

        msr = MSR.objects.create(
            project=project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '10000.00',
            },
            created_by=self.sales_associate,
            prepared_by=self.sales_associate,
            approved_by=self.comptroller,
        )

        project.current_approved = msr
        project.save(
            update_fields=['current_approved']
        )

        with self.assertRaises(ValidationError):
            calculate_gross_profit(
                project.id
            )

    def test_missing_approved_msr_is_rejected(self):
        self.project.current_approved = None
        self.project.save(
            update_fields=['current_approved']
        )

        with self.assertRaises(ValidationError):
            calculate_gross_profit(
                self.project.id
            )

    def test_draft_cost_record_is_not_used_for_profitability(self):
        ProjectCostRecord.objects.create(
            project=self.project,
            msr=self.msr,
            version=2,
            equipment_cost=Decimal('9000.00'),
            material_cost=Decimal('0.00'),
            dealer_fee=Decimal('0.00'),
            technician_cost=Decimal('0.00'),
            lead_cost=Decimal('0.00'),
            damon_cost=Decimal('0.00'),
            jerry_cost=Decimal('0.00'),
            created_by=self.sales_manager,
        )

        result = calculate_gross_profit(
            self.project.id
        )

        self.assertEqual(
            result['gross_profit'],
            Decimal('2000.00'),
        )

        self.assertEqual(
            result['cost_record_id'],
            str(self.cost_record.id),
        )
