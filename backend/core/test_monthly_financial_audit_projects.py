"""Isolated database tests for read-only monthly completed-project audit."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import (
    Customer,
    InstallationSchedule,
    Project,
    ProjectCostRecord,
    Role,
    User,
)
from .monthly_financial_audit_projects import (
    get_monthly_completed_project_audit,
)


class MonthlyFinancialAuditProjectTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.comptroller = User.objects.create_user(
            username="audit_comptroller",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="AC",
        )
        cls.other_user = User.objects.create_user(
            username="audit_other",
            password="test-password",
            role=Role.SALES_ASSOCIATE,
            initials="AO",
        )
        cls.customer = Customer.objects.create(
            legal_name="Audit Customer",
            billing_address="1 Audit Lane",
            created_by=cls.comptroller,
        )
        cls.project = Project.objects.create(
            code="AUDIT-PROJECT-001",
            customer=cls.customer,
            location="Audit Location",
            sales_associate=cls.comptroller,
            reviewer=cls.comptroller,
        )

    def make_schedule(self, project=None, day=15, month=10, year=2026):
        stamp = timezone.make_aware(
            datetime(year, month, day, 12, 0, 0),
            timezone.get_current_timezone(),
        )
        return InstallationSchedule.objects.create(
            project=project or self.project,
            scheduled_date=stamp.date(),
            status=InstallationSchedule.Status.COMPLETED,
            installation_manager=self.comptroller,
            scheduled_by=self.comptroller,
            completed_at=stamp,
        )

    def result(self, year=2026, month=10):
        return get_monthly_completed_project_audit(
            self.comptroller, year, month
        )

    def test_empty_month(self):
        result = self.result()
        self.assertEqual(result["completed_project_count"], 0)
        self.assertEqual(result["projects"], [])

    def test_completed_installation_included(self):
        schedule = self.make_schedule()
        result = self.result()
        self.assertEqual(result["completed_project_count"], 1)
        item = result["projects"][0]
        self.assertEqual(item["project_id"], str(self.project.pk))
        self.assertEqual(
            item["installation_schedule_id"], str(schedule.pk)
        )
        self.assertEqual(item["installation_status"], "COMPLETED")

    def test_adjacent_month_excluded(self):
        self.make_schedule(month=9)
        self.assertEqual(self.result()["completed_project_count"], 0)

    def test_first_and_last_days_included(self):
        self.make_schedule(day=1)
        other = Project.objects.create(
            code="AUDIT-PROJECT-002",
            customer=self.customer,
            location="Second Audit Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
        )
        self.make_schedule(project=other, day=31)
        self.assertEqual(self.result()["completed_project_count"], 2)

    def test_scheduled_installation_excluded(self):
        InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=timezone.localdate(),
            status=InstallationSchedule.Status.SCHEDULED,
            installation_manager=self.comptroller,
            scheduled_by=self.comptroller,
        )
        self.assertEqual(self.result()["completed_project_count"], 0)

    def test_certificate_not_assumed_verified(self):
        self.make_schedule()
        item = self.result()["projects"][0]
        self.assertEqual(
            item["completion_certificate_status"], "NOT_VERIFIED"
        )
        self.assertEqual(
            self.result()["certificate_verification_basis"],
            "NOT_YET_AUTHENTICATED",
        )

    def test_missing_cost_record_explicit(self):
        self.make_schedule()
        item = self.result()["projects"][0]
        self.assertIsNone(item["cost_record_id"])
        self.assertIsNone(item["cost_total"])
        self.assertTrue(all(
            amount is None
            for amount in item["cost_categories"].values()
        ))

    def test_duplicate_installation_records_one_project(self):
        self.make_schedule(day=10)
        self.make_schedule(day=11)
        self.assertEqual(self.result()["completed_project_count"], 1)

    def test_unauthorized_user_denied(self):
        with self.assertRaises(PermissionDenied):
            get_monthly_completed_project_audit(
                self.other_user, 2026, 10
            )

        with self.assertRaises(PermissionDenied):
            get_monthly_completed_project_audit(
                None, 2026, 10
            )

    def test_inactive_comptroller_denied(self):
        self.comptroller.is_active = False
        self.comptroller.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.result()
