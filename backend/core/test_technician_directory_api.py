"""Authorization and identity tests for the Technician directory API."""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Role, User


class TechnicianDirectoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username="directory_installation_manager",
            role=Role.INSTALLATION_MANAGER,
        )
        self.comptroller = User.objects.create_user(
            username="directory_comptroller",
            role=Role.COMPTROLLER,
        )
        self.ceo = User.objects.create_user(
            username="directory_ceo",
            role=Role.CEO,
        )
        self.sales_manager = User.objects.create_user(
            username="directory_sales_manager",
            role=Role.SALES_MANAGER,
        )
        self.sales_associate = User.objects.create_user(
            username="directory_sales_associate",
            role=Role.SALES_ASSOCIATE,
        )
        self.technician = User.objects.create_user(
            username="directory_technician",
            first_name="Jordan",
            last_name="Smith",
            role=Role.TECHNICIAN,
        )
        self.inactive_technician = User.objects.create_user(
            username="directory_inactive_technician",
            role=Role.TECHNICIAN,
            is_active=False,
        )

    def get_directory(self, actor):
        self.client.force_authenticate(user=actor)
        return self.client.get("/api/technicians/")

    def assert_authorized_directory(self, actor):
        response = self.get_directory(actor)
        self.assertEqual(response.status_code, 200)

        data = response.data
        if isinstance(data, dict) and "results" in data:
            data = data["results"]

        self.assertIsInstance(data, list)

        ids = {str(item["id"]) for item in data}
        self.assertIn(str(self.technician.pk), ids)
        self.assertNotIn(str(self.inactive_technician.pk), ids)
        self.assertEqual(ids, {str(self.technician.pk)})

        technician = next(
            item for item in data
            if str(item["id"]) == str(self.technician.pk)
        )
        self.assertEqual(technician["username"], "directory_technician")
        self.assertEqual(technician["first_name"], "Jordan")
        self.assertEqual(technician["last_name"], "Smith")

    def test_installation_manager_can_view_directory(self):
        self.assert_authorized_directory(self.manager)

    def test_comptroller_can_view_directory(self):
        self.assert_authorized_directory(self.comptroller)

    def test_ceo_can_view_directory_without_temporary_authority(self):
        self.assert_authorized_directory(self.ceo)

    def test_sales_manager_cannot_view_directory(self):
        response = self.get_directory(self.sales_manager)
        self.assertEqual(response.status_code, 403)

    def test_sales_associate_cannot_view_directory(self):
        response = self.get_directory(self.sales_associate)
        self.assertEqual(response.status_code, 403)

    def test_technician_cannot_view_directory(self):
        response = self.get_directory(self.technician)
        self.assertEqual(response.status_code, 403)

    def test_inactive_manager_cannot_view_directory(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        response = self.get_directory(self.manager)
        self.assertIn(response.status_code, (401, 403))

    def test_unauthenticated_user_cannot_view_directory(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/technicians/")
        self.assertIn(response.status_code, (401, 403))

    def test_ceo_directory_access_does_not_grant_assignment_authority(self):
        self.client.force_authenticate(self.ceo)
        directory = self.client.get("/api/technicians/")
        self.assertEqual(directory.status_code, 200)

        from .models import Customer, Project, ProjectTechnicalAssignment

        customer = Customer.objects.create(
            legal_name="Technician Directory Security Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        project = Project.objects.create(
            code="TECH-DIRECTORY-001",
            customer=customer,
            location="Security Test Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": "2026-10-10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProjectTechnicalAssignment.objects.exists())
