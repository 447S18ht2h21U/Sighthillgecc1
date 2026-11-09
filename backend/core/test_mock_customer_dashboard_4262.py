"""Mock-customer acceptance: actual MSR, dashboard API and PDF reviews.

Runs exclusively in Django's disposable SQLite test database.
Does not operate real signing, payments, delivery or completion.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Document, Role, User
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)
from .approved_document_lifecycle_integration_4249 import (
    inspect_integrated_document_lifecycle,
)


class MockCustomerDashboard4262Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def dashboard(self, actor):
        client = APIClient()
        client.force_authenticate(user=actor)
        response = client.get("/api/project-dashboard/")
        self.assertEqual(response.status_code, 200)
        cache_directives = {
            directive.strip().lower()
            for directive in response["Cache-Control"].split(",")
        }
        self.assertIn("no-store", cache_directives)
        self.assertIn("private", cache_directives)
        data = response.json()
        entries = list(data.get("needs_attention", []))
        for stage in data.get("stages", []):
            entries.extend(stage.get("projects", []))
        return entries

    def project_entries(self, actor):
        return [
            item for item in self.dashboard(actor)
            if str(item["id"]) == str(self.project.pk)
        ]

    def test_approved_fictional_msr_appears_on_dashboard(self):
        entries = self.project_entries(self.comptroller)
        self.assertTrue(entries, "Approved mock project must be visible.")
        for item in entries:
            self.assertEqual(item["code"], self.project.code)
            summary = item["workflow_evidence"]
            self.assertIs(summary["read_only"], True)
            self.assertEqual(
                summary["statuses"]["approved_msr"], "VERIFIED"
            )
            self.assertIs(summary["installation_authorized"], False)
            self.assertIs(
                summary["project_completion_authorized"], False
            )

    def test_other_sales_associate_cannot_view_mock_project(self):
        other = User.objects.create_user(
            username="mock4262_other",
            password="synthetic-only",
            role=Role.SALES_ASSOCIATE,
            initials="MO",
        )
        entries = self.project_entries(other)
        self.assertEqual(entries, [])

    def test_actual_six_pdf_previews_do_not_claim_delivery(self):
        batch = RealLifecycleIntegration4249Tests.render(self)
        report = inspect_integrated_document_lifecycle(batch)

        self.assertEqual(len(report.documents), 6)
        self.assertTrue(all(
            item.preview_verified for item in report.documents
        ))
        self.assertEqual(Document.objects.count(), 0)

        entries = self.project_entries(self.comptroller)
        self.assertTrue(entries)
        for item in entries:
            statuses = item["workflow_evidence"]["statuses"]
            self.assertEqual(
                statuses["receipt_delivery"], "NOT_EVALUATED"
            )
            self.assertEqual(
                statuses["completed_docusign"], "NOT_EVALUATED"
            )
            self.assertEqual(
                statuses["project_completion"], "BLOCKED"
            )