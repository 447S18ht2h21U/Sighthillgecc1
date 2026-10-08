from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.db import DatabaseError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Customer,
    Project,
    MSR,
    ProjectCostRecord,
    Role,
    User,
)
from .project_cost_services import approve_project_cost_record


class ProjectCostRecordTests(TestCase):

    def setUp(self):
        self.comptroller = User.objects.create_user(
            username='cost_comptroller',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.sales_manager = User.objects.create_user(
            username='cost_sales_manager',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.sales_associate = User.objects.create_user(
            username='cost_sales_associate',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.customer = Customer.objects.create(
            legal_name='Cost Test Customer',
            billing_address='123 Cost Test Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='COST-TEST-001',
            customer=self.customer,
            location='Cost test location',
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

    def test_comptroller_can_approve_project_cost_record(self):
        approved = approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

        self.assertEqual(
            approved.status,
            ProjectCostRecord.Status.APPROVED,
        )
        self.assertEqual(
            approved.approved_by_id,
            self.comptroller.id,
        )
        self.assertIsNotNone(
            approved.approved_at
        )

    def test_sales_manager_cannot_approve_project_cost_record(self):
        with self.assertRaises(PermissionDenied):
            approve_project_cost_record(
                self.sales_manager,
                self.cost_record.id,
            )

        self.cost_record.refresh_from_db()

        self.assertEqual(
            self.cost_record.status,
            ProjectCostRecord.Status.DRAFT,
        )
        self.assertIsNone(
            self.cost_record.approved_by,
        )
        self.assertIsNone(
            self.cost_record.approved_at,
        )

    def test_negative_project_cost_is_rejected(self):
        from django.db import DatabaseError, transaction

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ProjectCostRecord.objects.filter(
                    pk=self.cost_record.id,
                ).update(
                    equipment_cost=Decimal('-1.00'),
                )

        self.cost_record.refresh_from_db()

        self.assertEqual(
            self.cost_record.equipment_cost,
            Decimal('2000.00'),
        )
        self.assertEqual(
            self.cost_record.status,
            ProjectCostRecord.Status.DRAFT,
        )

    def test_approved_project_costs_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ProjectCostRecord.objects.filter(
                    pk=self.cost_record.id,
                ).update(
                    equipment_cost=Decimal('9999.00'),
                )

        self.cost_record.refresh_from_db()

        self.assertEqual(
            self.cost_record.status,
            ProjectCostRecord.Status.APPROVED,
        )
        self.assertEqual(
            self.cost_record.equipment_cost,
            Decimal('2000.00'),
        )

    def test_approved_project_costs_cannot_be_modified(self):
        from django.db import DatabaseError, transaction

        approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ProjectCostRecord.objects.filter(
                    pk=self.cost_record.id,
                ).update(
                    equipment_cost=Decimal('9999.00'),
                )

        self.cost_record.refresh_from_db()

        self.assertEqual(
            self.cost_record.status,
            ProjectCostRecord.Status.APPROVED,
        )
        self.assertEqual(
            self.cost_record.equipment_cost,
            Decimal('2000.00'),
        )

    def test_approved_project_costs_cannot_be_deleted(self):
        from django.db import DatabaseError, transaction

        approve_project_cost_record(
            self.comptroller,
            self.cost_record.id,
        )

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ProjectCostRecord.objects.filter(
                    pk=self.cost_record.id,
                ).delete()

        self.cost_record.refresh_from_db()

        self.assertEqual(
            self.cost_record.status,
            ProjectCostRecord.Status.APPROVED,
        )
        self.assertEqual(
            self.cost_record.equipment_cost,
            Decimal('2000.00'),
        )

    def test_cannot_insert_approved_project_cost_record_directly(self):
        from django.db import DatabaseError, transaction
        from django.utils import timezone

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ProjectCostRecord.objects.create(
                    project=self.project,
                    msr=self.msr,
                    version=2,
                    equipment_cost=Decimal('1000.00'),
                    material_cost=Decimal('500.00'),
                    dealer_fee=Decimal('100.00'),
                    technician_cost=Decimal('200.00'),
                    lead_cost=Decimal('3000.00'),
                    damon_cost=Decimal('500.00'),
                    jerry_cost=Decimal('250.00'),
                    status=ProjectCostRecord.Status.APPROVED,
                    created_by=self.sales_manager,
                    approved_by=self.comptroller,
                    approved_at=timezone.now(),
                )

        self.assertFalse(
            ProjectCostRecord.objects.filter(
                version=2,
            ).exists()
        )