from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Customer, Project, ProjectSalesStatusChange, User
from .sales_status_api_5002 import SalesStatusDetail


class SalesStatusApi5002Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="status_api_manager_5002",
            role="SALES_MANAGER",
        )
        cls.associate = User.objects.create_user(
            username="status_api_associate_5002",
            role="SALES_ASSOCIATE",
        )
        cls.comptroller = User.objects.create_user(
            username="status_api_comptroller_5002",
            role="COMPTROLLER",
        )
        cls.customer = Customer.objects.create(
            legal_name="Isolated Status API Customer",
            billing_address="Acceptance Test Only",
            created_by=cls.manager,
        )
        cls.project = Project.objects.create(
            code="ISOLATED-STATUS-API-5002",
            customer=cls.customer,
            location="Acceptance Test Only",
            sales_associate=cls.associate,
            reviewer=cls.comptroller,
        )

    def request(self, method, actor, data=None):
        path = "/test-only/sales-status/"
        factory = APIRequestFactory()
        if method == "POST":
            req = factory.post(path, data or {}, format="json")
        else:
            req = factory.get(path)
        force_authenticate(req, user=actor)
        return SalesStatusDetail.as_view()(
            req, project_id=self.project.pk
        )

    def test_manager_can_change_status_without_changing_project_state(self):
        response = self.request("POST", self.manager, {
            "sales_status": "LOST",
            "reason": "Customer declined the proposal",
        })
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.sales_status, "LOST")
        self.assertEqual(self.project.state, "DRAFT")
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 1)

    def test_comptroller_cannot_change_status(self):
        response = self.request("POST", self.comptroller, {
            "sales_status": "LOST",
            "reason": "Customer declined the proposal",
        })
        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 0)

    def test_invalid_status_creates_no_history(self):
        response = self.request("POST", self.manager, {
            "sales_status": "COMPLETED",
            "reason": "Not a commercial opportunity status",
        })
        self.assertIn(response.status_code, (400, 403, 404))
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 0)

    def test_history_is_available_to_authorized_scope(self):
        response = self.request("GET", self.manager)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["history"], [])
        self.assertIsNone(response.data["sales_status"])

    def test_endpoint_is_not_registered_for_live_requests(self):
        from django.urls import resolve, Resolver404
        with self.assertRaises(Resolver404):
            resolve("/api/test-only/sales-status/")
