from decimal import Decimal

from django.test import TestCase

from .commission_services import calculate_commissions
from .models import (
    Customer,
    Project,
    MSR,
    ProjectCostRecord,
    Role,
    User,
)
from .project_cost_services import approve_project_cost_record


class CommissionTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username='commission_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.sales_manager = User.objects.create_user(
            username='commission_sales_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_associate = User.objects.create_user(
            username='commission_sales_associate',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.customer = Customer.objects.create(
            legal_name='Commission Test Customer',
            billing_address='123 Commission Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='COMMISSION-TEST-001',
            customer=self.customer,
            location='Commission test location',
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

    def test_calculates_positive_profit_commissions(self):
        result = calculate_commissions(
            self.project.id
        )

        self.assertEqual(
            result['gross_profit'],
            Decimal('2000.00'),
        )

        self.assertEqual(
            result['ryan_commission'],
            Decimal('300.00'),
        )

        self.assertEqual(
            result['doug_commission'],
            Decimal('100.00'),
        )

        self.assertEqual(
            result['net_profit'],
            Decimal('1600.00'),
        )

        self.assertEqual(
            result['calculation_snapshot']['ryan_rate'],
            '0.15',
        )

        self.assertEqual(
            result['calculation_snapshot']['doug_rate'],
            '0.05',
        )

    def test_calculates_positive_profit_commissions(self):
        result = calculate_commissions(
            self.project.id
        )

        self.assertEqual(
            result['gross_profit'],
            Decimal('2000.00'),
        )

        self.assertEqual(
            result['ryan_commission'],
            Decimal('300.00'),
        )

        self.assertEqual(
            result['doug_commission'],
            Decimal('100.00'),
        )

        self.assertEqual(
            result['net_profit'],
            Decimal('1600.00'),
        )

        self.assertEqual(
            result['calculation_snapshot']['ryan_rate'],
            '0.15',
        )

        self.assertEqual(
            result['calculation_snapshot']['doug_rate'],
            '0.05',
        )

    def test_no_variable_commission_when_gross_profit_is_negative(self):
        negative_project = Project.objects.create(
            code='COMMISSION-NEGATIVE-001',
            customer=self.customer,
            location='Negative profit location',
            sales_associate=self.sales_associate,
            reviewer=self.sales_manager,
            state='APPROVED',
        )

        negative_msr = MSR.objects.create(
            project=negative_project,
            number=1,
            status='APPROVED',
            snapshot={
                'total_price': '5000.00',
            },
            created_by=self.sales_associate,
            prepared_by=self.sales_associate,
            approved_by=self.comptroller,
        )

        negative_project.current_approved = negative_msr
        negative_project.save(
            update_fields=['current_approved']
        )

        negative_cost = ProjectCostRecord.objects.create(
            project=negative_project,
            msr=negative_msr,
            version=1,
            equipment_cost=Decimal('10000.00'),
            material_cost=Decimal('0.00'),
            dealer_fee=Decimal('0.00'),
            technician_cost=Decimal('0.00'),
            lead_cost=Decimal('0.00'),
            damon_cost=Decimal('0.00'),
            jerry_cost=Decimal('0.00'),
            created_by=self.sales_manager,
        )

        approve_project_cost_record(
            self.comptroller,
            negative_cost.id,
        )

        result = calculate_commissions(
            negative_project.id
        )

        self.assertEqual(
            result['gross_profit'],
            Decimal('-5000.00'),
        )

        self.assertEqual(
            result['ryan_commission'],
            Decimal('0.00'),
        )

        self.assertEqual(
            result['doug_commission'],
            Decimal('0.00'),
        )

        self.assertEqual(
            result['net_profit'],
            Decimal('-5000.00'),
        )