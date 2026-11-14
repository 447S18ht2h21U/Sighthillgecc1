from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from .models import Customer, Project, ProjectSalesStatusChange, User
from .sales_status_service_5000 import change_project_sales_status


class SalesStatusDatabaseAcceptance5001(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="sales_status_manager_5001",
            role="SALES_MANAGER",
        )
        cls.associate = User.objects.create_user(
            username="sales_status_associate_5001",
            role="SALES_ASSOCIATE",
        )
        cls.reviewer = User.objects.create_user(
            username="sales_status_reviewer_5001",
            role="COMPTROLLER",
        )
        cls.customer = Customer.objects.create(
            legal_name="Isolated Sales Status Customer",
            billing_address="Acceptance Test Only",
            created_by=cls.manager,
        )
        cls.project = Project.objects.create(
            code="ISOLATED-SALES-5001",
            customer=cls.customer,
            location="Acceptance Test Only",
            sales_associate=cls.associate,
            reviewer=cls.reviewer,
        )

    def test_sales_status_update_preserves_project_state_and_customer(self):
        original_state = self.project.state
        original_customer = self.project.customer_id

        audit = change_project_sales_status(
            actor=self.manager,
            project_id=self.project.pk,
            new_status="LOST",
            reason="Customer declined this proposal",
        )

        self.project.refresh_from_db()
        self.assertEqual(self.project.sales_status, "LOST")
        self.assertEqual(self.project.state, original_state)
        self.assertEqual(self.project.customer_id, original_customer)
        self.assertEqual(audit.previous_status, None)
        self.assertEqual(audit.new_status, "LOST")
        self.assertEqual(audit.changed_by_id, self.manager.pk)
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 1)

    def test_unauthorized_change_creates_no_history(self):
        with self.assertRaises(PermissionDenied):
            change_project_sales_status(
                actor=self.associate,
                project_id=self.project.pk,
                new_status="LOST",
                reason="Customer declined this proposal",
            )
        self.project.refresh_from_db()
        self.assertIsNone(self.project.sales_status)
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 0)

    def test_duplicate_status_rejected_without_duplicate_history(self):
        change_project_sales_status(
            actor=self.manager,
            project_id=self.project.pk,
            new_status="INACTIVE",
            reason="Customer requested later follow-up",
        )
        with self.assertRaises(ValidationError):
            change_project_sales_status(
                actor=self.manager,
                project_id=self.project.pk,
                new_status="INACTIVE",
                reason="Duplicate customer disposition request",
            )
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 1)

    def test_status_changes_preserve_sequence_and_prior_history(self):
        change_project_sales_status(
            actor=self.manager,
            project_id=self.project.pk,
            new_status="INACTIVE",
            reason="Customer requested later follow-up",
        )
        change_project_sales_status(
            actor=self.manager,
            project_id=self.project.pk,
            new_status="ACTIVE",
            reason="Customer resumed sales discussions",
        )
        rows = list(
            ProjectSalesStatusChange.objects.order_by("pk")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [(r.previous_status, r.new_status) for r in rows],
            [(None, "INACTIVE"), ("INACTIVE", "ACTIVE")],
        )

    def test_audit_instance_cannot_be_edited_or_deleted(self):
        row = change_project_sales_status(
            actor=self.manager,
            project_id=self.project.pk,
            new_status="CANCELLED",
            reason="Customer cancelled opportunity",
        )
        with self.assertRaises(ValueError):
            row.save()
        with self.assertRaises(ValueError):
            row.delete()
        self.assertEqual(
            ProjectSalesStatusChange.objects.count(), 1
        )