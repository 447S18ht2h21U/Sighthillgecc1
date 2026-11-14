import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Customer, Project, ProjectSalesStatusChange, User


@override_settings(DEBUG=True)
class ControlledSalesStatusRoute5004Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="sales_route_manager_5004",
            role="SALES_MANAGER",
        )
        cls.associate = User.objects.create_user(
            username="sales_route_associate_5004",
            role="SALES_ASSOCIATE",
        )
        cls.reviewer = User.objects.create_user(
            username="sales_route_reviewer_5004",
            role="COMPTROLLER",
        )
        cls.customer = Customer.objects.create(
            legal_name="Isolated Route Customer",
            billing_address="Test Only",
            created_by=cls.manager,
        )
        cls.project = Project.objects.create(
            code="ISOLATED-ROUTE-5004",
            customer=cls.customer,
            location="Test Only",
            sales_associate=cls.associate,
            reviewer=cls.reviewer,
        )

    def call_route(self, method, actor, data=None):
        url = (
            f"/api/projects/{self.project.pk}/"
            "sales-status/"
        )
        factory = APIRequestFactory()
        request = (
            factory.post(url, data, format="json")
            if method == "POST"
            else factory.get(url)
        )
        if actor is not None:
            force_authenticate(request, user=actor)

        match = resolve(url)
        self.assertEqual(match.url_name, "veridian-sales-status-5004")
        return match.func(request, **match.kwargs)

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"GECC_SALES_STATUS_ENABLED": "0"}):
            response = self.call_route("GET", self.manager)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_is_denied(self):
        with patch.dict(os.environ, {"GECC_SALES_STATUS_ENABLED": "1"}):
            response = self.call_route("GET", None)
        self.assertIn(response.status_code, (401, 403))

    def test_authorized_read_with_isolated_feature_enabled(self):
        with patch.dict(os.environ, {"GECC_SALES_STATUS_ENABLED": "1"}):
            response = self.call_route("GET", self.manager)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["sales_status"])
        self.assertEqual(response.data["project_state"], "DRAFT")

    def test_manager_transition_creates_exactly_one_audit(self):
        with patch.dict(os.environ, {"GECC_SALES_STATUS_ENABLED": "1"}):
            response = self.call_route(
                "POST",
                self.manager,
                {
                    "sales_status": "LOST",
                    "reason": "Customer declined the proposal",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 1)
        self.project.refresh_from_db()
        self.assertEqual(self.project.sales_status, "LOST")
        self.assertEqual(self.project.state, "DRAFT")

    def test_comptroller_cannot_change_sales_status(self):
        with patch.dict(os.environ, {"GECC_SALES_STATUS_ENABLED": "1"}):
            response = self.call_route(
                "POST",
                self.reviewer,
                {
                    "sales_status": "LOST",
                    "reason": "Customer declined the proposal",
                },
            )
        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(ProjectSalesStatusChange.objects.count(), 0)
