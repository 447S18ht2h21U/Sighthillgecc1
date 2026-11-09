"""Authenticated project dashboard evidence visibility regression.

Uses only Django's disposable in-memory test database.
No production routes, document releases, or migrations are added.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Customer, Project, Role, User


class DashboardWorkflowHTTP4260Tests(TestCase):
    def setUp(self):
        self.sales_one = User.objects.create_user(
            username="wf4260_sales_one",
            password="synthetic-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="WA",
        )
        self.sales_two = User.objects.create_user(
            username="wf4260_sales_two",
            password="synthetic-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="WB",
        )
        self.comptroller = User.objects.create_user(
            username="wf4260_comptroller",
            password="synthetic-test-only",
            role=Role.COMPTROLLER,
            initials="WC",
        )
        self.first = self.make_project(
            "WF4260-001", self.sales_one
        )
        self.second = self.make_project(
            "WF4260-002", self.sales_two
        )

    def make_project(self, code, associate):
        customer = Customer.objects.create(
            legal_name="Fictional " + code,
            created_by=associate,
        )
        return Project.objects.create(
            code=code,
            customer=customer,
            location="Synthetic Test Location",
            sales_associate=associate,
            reviewer=self.comptroller,
        )

    def request_as(self, actor):
        client = APIClient()
        if actor is not None:
            client.force_authenticate(user=actor)
        return client.get("/api/project-dashboard/")

    def projects(self, response):
        data = response.json()
        entries = list(data.get("needs_attention", []))
        for stage in data.get("stages", []):
            entries.extend(stage.get("projects", []))
        return entries

    def test_unauthenticated_request_is_denied(self):
        response = self.request_as(None)
        self.assertIn(response.status_code, (401, 403))

    def test_sales_associate_cannot_see_another_project(self):
        for actor, allowed, forbidden in (
            (self.sales_one, self.first, self.second),
            (self.sales_two, self.second, self.first),
        ):
            with self.subTest(actor=actor.username):
                response = self.request_as(actor)
                self.assertEqual(response.status_code, 200)

                entries = self.projects(response)
                identifiers = {str(item["id"]) for item in entries}

                self.assertIn(str(allowed.pk), identifiers)
                self.assertNotIn(str(forbidden.pk), identifiers)

                for item in entries:
                    self.assertIn("workflow_evidence", item)
                    evidence = item["workflow_evidence"]
                    self.assertIs(evidence["read_only"], True)
                    self.assertIs(
                        evidence["installation_authorized"], False
                    )
                    self.assertIs(
                        evidence["project_completion_authorized"], False
                    )
                    self.assertEqual(
                        evidence["statuses"]["project_completion"],
                        "BLOCKED",
                    )

    def test_comptroller_sees_both_scoped_projects(self):
        response = self.request_as(self.comptroller)
        self.assertEqual(response.status_code, 200)

        identifiers = {
            str(item["id"])
            for item in self.projects(response)
        }
        self.assertIn(str(self.first.pk), identifiers)
        self.assertIn(str(self.second.pk), identifiers)

    def test_no_approved_msr_never_infers_evidence(self):
        response = self.request_as(self.sales_one)
        self.assertEqual(response.status_code, 200)

        entries = [
            item for item in self.projects(response)
            if str(item["id"]) == str(self.first.pk)
        ]
        self.assertTrue(entries)

        for item in entries:
            statuses = item["workflow_evidence"]["statuses"]
            self.assertEqual(statuses["approved_msr"], "BLOCKED")
            self.assertEqual(
                statuses["receipt_delivery"], "NOT_EVALUATED"
            )
            self.assertEqual(
                statuses["completed_docusign"], "NOT_EVALUATED"
            )
            self.assertEqual(
                statuses["project_completion"], "BLOCKED"
            )