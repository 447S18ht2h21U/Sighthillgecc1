from django.test import SimpleTestCase

from .models import Project


class ProjectSalesStatus4995Tests(SimpleTestCase):
    def test_commercial_status_is_separate_from_operational_state(self):
        self.assertIsNot(
            Project._meta.get_field("sales_status"),
            Project._meta.get_field("state"),
        )

    def test_historical_records_are_not_assigned_an_invented_outcome(self):
        self.assertIsNone(Project._meta.get_field("sales_status").get_default())

    def test_approved_sales_status_values(self):
        self.assertEqual(
            set(Project.SalesStatus.values),
            {"ACTIVE", "WON", "LOST", "CANCELLED", "INACTIVE"},
        )

    def test_existing_project_state_is_preserved(self):
        self.assertEqual(Project._meta.get_field("state").get_default(), "DRAFT")

    def test_status_does_not_archive_customer_or_remove_project(self):
        self.assertIsNotNone(Project._meta.get_field("customer"))
        from .models import Customer
        self.assertIsNotNone(Customer._meta.get_field("archived"))
