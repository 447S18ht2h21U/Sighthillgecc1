"""Isolated integration tests for the registered read-only MSR endpoint."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import (
    Customer, MSR, Project, ProjectTechnicalAssignment, Role, User,
)
from .visible_msr_api import VisibleMSRViewSet


class VisibleMSRAPITests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.comptroller = User.objects.create_user(
            username="visible_msr_comptroller", role=Role.COMPTROLLER,
        )
        self.sales = User.objects.create_user(
            username="visible_msr_sales", role=Role.SALES_ASSOCIATE,
        )
        self.other_sales = User.objects.create_user(
            username="visible_msr_other_sales", role=Role.SALES_ASSOCIATE,
        )
        self.technician = User.objects.create_user(
            username="visible_msr_technician", role=Role.TECHNICIAN,
        )
        self.manager = User.objects.create_user(
            username="visible_msr_manager", role=Role.INSTALLATION_MANAGER,
        )
        self.marketing = User.objects.create_user(
            username="visible_msr_marketing", role=Role.MARKETING,
        )
        self.dba = User.objects.create_user(
            username="visible_msr_dba", role=Role.DATABASE_ADMINISTRATOR,
        )

        customer = Customer.objects.create(
            legal_name="Visible MSR API Test Customer",
            billing_address="20 Fixture Avenue",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="VISIBLE-MSR-001",
            customer=customer,
            location="20 Fixture Avenue",
            sales_associate=self.sales,
            reviewer=self.comptroller,
        )
        self.other_project = Project.objects.create(
            code="VISIBLE-MSR-002",
            customer=customer,
            location="22 Fixture Avenue",
            sales_associate=self.other_sales,
            reviewer=self.comptroller,
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            created_by=self.sales,
            prepared_by=self.sales,
            snapshot={
                "scope": "Authorized installation",
                "total_price": "10000.00",
                "restricted_financial_secret": "MUST_NOT_LEAK",
            },
        )
        self.other_msr = MSR.objects.create(
            project=self.other_project,
            number=1,
            created_by=self.other_sales,
            prepared_by=self.other_sales,
            snapshot={"scope": "Other project"},
        )

    def request(self, actor, method="get", detail=False, pk=None):
        view = VisibleMSRViewSet.as_view(
            {"get": "retrieve"} if detail else {"get": "list"}
        )
        url = "/api/visible-msrs/"
        if detail:
            url += str(pk) + "/"
        req = getattr(self.factory, method)(url)
        if actor is not None:
            force_authenticate(req, user=actor)
        return view(req, pk=pk) if detail else view(req)

    def results(self, response):
        data = response.data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def test_comptroller_sees_both_records(self):
        response = self.request(self.comptroller)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {str(item["id"]) for item in self.results(response)},
            {str(self.msr.pk), str(self.other_msr.pk)},
        )

    def test_marketing_sees_both_records(self):
        response = self.request(self.marketing)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.results(response)), 2)

    def test_sales_sees_only_owned_project(self):
        response = self.request(self.sales)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {str(item["id"]) for item in self.results(response)},
            {str(self.msr.pk)},
        )

    def test_technician_without_assignment_sees_none(self):
        response = self.request(self.technician)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.results(response)), 0)

    def test_active_technician_sees_assigned_project(self):
        ProjectTechnicalAssignment.objects.create(
            project=self.project,
            technical_associate=self.technician,
            assigned_by=self.manager,
            effective_date=timezone.localdate(),
            status=ProjectTechnicalAssignment.Status.ACTIVE,
        )
        response = self.request(self.technician)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {str(item["id"]) for item in self.results(response)},
            {str(self.msr.pk)},
        )

    def test_future_assignment_does_not_grant_access(self):
        ProjectTechnicalAssignment.objects.create(
            project=self.project,
            technical_associate=self.technician,
            assigned_by=self.manager,
            effective_date=timezone.localdate() + timedelta(days=1),
            status=ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertEqual(
            len(self.results(self.request(self.technician))), 0
        )

    def test_unauthorized_position_is_denied(self):
        self.assertEqual(self.request(self.dba).status_code, 403)

    def test_inactive_account_is_denied(self):
        self.sales.is_active = False
        self.sales.save(update_fields=["is_active"])
        self.assertEqual(self.request(self.sales).status_code, 403)

    def test_current_role_is_refreshed_from_database(self):
        stale_actor = User.objects.get(pk=self.sales.pk)
        User.objects.filter(pk=self.sales.pk).update(
            role=Role.DATABASE_ADMINISTRATOR
        )
        self.assertEqual(self.request(stale_actor).status_code, 403)

    def test_unauthenticated_request_is_denied(self):
        self.assertIn(self.request(None).status_code, (401, 403))

    def test_other_project_detail_is_not_exposed(self):
        self.assertEqual(
            self.request(
                self.sales, detail=True, pk=self.other_msr.pk
            ).status_code,
            404,
        )

    def test_snapshot_restricts_unapproved_fields(self):
        response = self.request(
            self.comptroller, detail=True, pk=self.msr.pk
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("scope", response.data["snapshot"])
        self.assertNotIn(
            "restricted_financial_secret", response.data["snapshot"]
        )

    def test_response_disables_caching(self):
        response = self.request(self.comptroller)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(
            response["X-Content-Type-Options"], "nosniff"
        )

    def test_write_methods_are_not_exposed(self):
        actions = VisibleMSRViewSet.http_method_names
        self.assertNotIn("post", actions)
        self.assertNotIn("put", actions)
        self.assertNotIn("patch", actions)
        self.assertNotIn("delete", actions)

    def test_serializer_enforces_complete_commercial_allowlist(self):
        from types import SimpleNamespace
        from .marketing_msr_api import MarketingMSRSerializer
        from .services import SNAPSHOT_FIELDS

        restricted = {
            "gross_profit": "9000.00",
            "net_profit": "7000.00",
            "commission": "1500.00",
            "technician_cost": "800.00",
            "dealer_fee": "200.00",
            "lead_cost": "3000.00",
            "restricted_financial_secret": "MUST_NOT_LEAK",
        }
        source = {key: "COMMERCIAL VALUE" for key in SNAPSHOT_FIELDS}
        source.update(restricted)
        serializer = MarketingMSRSerializer()
        result = serializer.get_snapshot(SimpleNamespace(snapshot=source))

        self.assertEqual(set(result), set(SNAPSHOT_FIELDS))
        for key in restricted:
            with self.subTest(field=key):
                self.assertNotIn(key, result)
        self.assertEqual(source["gross_profit"], "9000.00")

    def test_role_scoped_api_returns_only_commercial_snapshot_keys(self):
        from .services import SNAPSHOT_FIELDS

        for actor in (self.comptroller, self.marketing, self.sales):
            with self.subTest(role=actor.role):
                response = self.request(
                    actor, detail=True, pk=self.msr.pk
                )
                self.assertEqual(response.status_code, 200)
                snapshot = response.data["snapshot"]
                self.assertEqual(
                    set(snapshot), {"scope", "total_price"}
                )
                self.assertTrue(set(snapshot) <= SNAPSHOT_FIELDS)
                self.assertNotIn(
                    "restricted_financial_secret", snapshot
                )
