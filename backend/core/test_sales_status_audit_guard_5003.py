from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from .models import Customer, Project, ProjectSalesStatusChange, User
from .sales_status_service_5000 import change_project_sales_status


class SalesStatusAuditGuard5003Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="sales_guard_manager_5003",
            role="SALES_MANAGER",
        )
        cls.associate = User.objects.create_user(
            username="sales_guard_associate_5003",
            role="SALES_ASSOCIATE",
        )
        cls.reviewer = User.objects.create_user(
            username="sales_guard_reviewer_5003",
            role="COMPTROLLER",
        )
        cls.customer = Customer.objects.create(
            legal_name="Isolated Sales Audit Customer",
            billing_address="Disposable Test Only",
            created_by=cls.manager,
        )
        cls.project = Project.objects.create(
            code="ISOLATED-SALES-GUARD-5003",
            customer=cls.customer,
            location="Disposable Test Only",
            sales_associate=cls.associate,
            reviewer=cls.reviewer,
        )

    def create_audit(self):
        return change_project_sales_status(
            actor=self.manager,
            project_id=self.project.pk,
            new_status="LOST",
            reason="Customer declined this proposal",
        )

    def test_normal_status_change_still_creates_audit(self):
        record = self.create_audit()
        self.assertEqual(record.previous_status, None)
        self.assertEqual(record.new_status, "LOST")
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 1)

    def test_bulk_update_is_rejected_by_database(self):
        record = self.create_audit()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ProjectSalesStatusChange.objects.filter(
                    pk=record.pk
                ).update(reason="Unauthorized replacement")
        record.refresh_from_db()
        self.assertEqual(
            record.reason, "Customer declined this proposal"
        )

    def test_bulk_delete_is_rejected_by_database(self):
        record = self.create_audit()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ProjectSalesStatusChange.objects.filter(
                    pk=record.pk
                ).delete()
        self.assertTrue(
            ProjectSalesStatusChange.objects.filter(
                pk=record.pk
            ).exists()
        )

    def test_raw_sql_update_is_rejected(self):
        record = self.create_audit()
        table = connection.ops.quote_name(
            ProjectSalesStatusChange._meta.db_table
        )
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE " + table +
                        " SET reason = %s WHERE id = %s",
                        ["Unauthorized replacement", record.pk],
                    )
        record.refresh_from_db()
        self.assertEqual(
            record.reason, "Customer declined this proposal"
        )

    def test_raw_sql_delete_is_rejected(self):
        record = self.create_audit()
        table = connection.ops.quote_name(
            ProjectSalesStatusChange._meta.db_table
        )
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM " + table + " WHERE id = %s",
                        [record.pk],
                    )
        self.assertTrue(
            ProjectSalesStatusChange.objects.filter(
                pk=record.pk
            ).exists()
        )
