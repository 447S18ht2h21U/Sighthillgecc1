"""Security regression tests for the read-only operational project API."""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Customer, Project, ProjectTechnicalAssignment, Role, User

class OperationalProjectAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.comptroller = User.objects.create_user(username="op_api_comptroller", role=Role.COMPTROLLER)
        self.manager = User.objects.create_user(username="op_api_manager", role=Role.INSTALLATION_MANAGER)
        self.sales = User.objects.create_user(username="op_api_sales", role=Role.SALES_ASSOCIATE)
        self.other_sales = User.objects.create_user(username="op_api_other_sales", role=Role.SALES_ASSOCIATE)
        self.technician = User.objects.create_user(username="op_api_technician", role=Role.TECHNICIAN)
        self.unrelated = User.objects.create_user(username="op_api_unrelated", role=Role.DATABASE_ADMINISTRATOR)
        customer = Customer.objects.create(legal_name="Operational API Customer", billing_address="10 Test Road", created_by=self.comptroller)
        self.project = Project.objects.create(code="OP-API-001", customer=customer, location="10 Test Road", sales_associate=self.sales, reviewer=self.comptroller)
        self.other_project = Project.objects.create(code="OP-API-002", customer=customer, location="12 Test Road", sales_associate=self.other_sales, reviewer=self.comptroller)

    def project_ids(self, user):
        self.client.force_authenticate(user)
        response = self.client.get("/api/operational-projects/")
        self.assertEqual(response.status_code, 200)
        return {item["id"] for item in response.data["results"]}

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get("/api/operational-projects/")
        self.assertIn(response.status_code, (401, 403))

    def test_managers_see_all_projects(self):
        expected = {str(self.project.pk), str(self.other_project.pk)}
        for user in (self.comptroller, self.manager):
            with self.subTest(role=user.role):
                self.assertEqual(self.project_ids(user), expected)

    def test_sales_associate_sees_only_assigned_project(self):
        self.assertEqual(self.project_ids(self.sales), {str(self.project.pk)})

    def test_technician_sees_only_active_assigned_project(self):
        ProjectTechnicalAssignment.objects.create(
            project=self.project, technical_associate=self.technician,
            assigned_by=self.manager, effective_date=timezone.localdate(),
            status=ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertEqual(self.project_ids(self.technician), {str(self.project.pk)})

    def test_unrelated_role_sees_no_projects(self):
        self.assertEqual(self.project_ids(self.unrelated), set())

    def test_out_of_scope_project_detail_is_not_accessible(self):
        self.client.force_authenticate(self.sales)
        response = self.client.get(f"/api/operational-projects/{self.other_project.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_response_excludes_commercial_records(self):
        self.client.force_authenticate(self.comptroller)
        response = self.client.get(f"/api/operational-projects/{self.project.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("current_approved", response.data)
        self.assertNotIn("pending", response.data)
        self.assertNotIn("snapshot", response.data)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_endpoint_is_read_only(self):
        self.client.force_authenticate(self.comptroller)
        response = self.client.post("/api/operational-projects/", {}, format="json")
        self.assertEqual(response.status_code, 405)
