"""HTTP security tests for the registered read-only Visible MSR router."""

import time

from django.test import TestCase, override_settings

from .models import MSR
from . import test_visible_msr_api as visible_msr_fixture


@override_settings(ROOT_URLCONF="config.urls")
class VisibleMSRHTTPTests(TestCase):
    """Test real HTTP routing without changing production application URLs."""

    def setUp(self):
        # Reuse the same verified user, project, and MSR fixtures.
        visible_msr_fixture.VisibleMSRAPITests.setUp(self)

    def authenticate(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session["last_activity"] = time.time()
        session.save()

    def list_results(self, response):
        body = response.json()
        return body["results"] if isinstance(body, dict) and "results" in body else body

    def test_comptroller_http_list_sees_both_projects(self):
        self.authenticate(self.comptroller)
        response = self.client.get("/api/visible-msrs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {str(item["id"]) for item in self.list_results(response)},
            {str(self.msr.pk), str(self.other_msr.pk)},
        )

    def test_sales_http_list_is_project_scoped(self):
        self.authenticate(self.sales)
        response = self.client.get("/api/visible-msrs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {str(item["id"]) for item in self.list_results(response)},
            {str(self.msr.pk)},
        )

    def test_marketing_http_list_sees_both_projects(self):
        self.authenticate(self.marketing)
        response = self.client.get("/api/visible-msrs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.list_results(response)), 2)

    def test_unauthorized_position_cannot_list(self):
        self.authenticate(self.dba)
        response = self.client.get("/api/visible-msrs/")
        self.assertEqual(response.status_code, 403)

    def test_anonymous_http_request_is_denied(self):
        response = self.client.get("/api/visible-msrs/")
        self.assertIn(response.status_code, (401, 403))

    def test_other_project_detail_is_hidden(self):
        self.authenticate(self.sales)
        response = self.client.get(
            f"/api/visible-msrs/{self.other_msr.pk}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_http_response_excludes_restricted_snapshot_fields(self):
        self.authenticate(self.comptroller)
        response = self.client.get(f"/api/visible-msrs/{self.msr.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("scope", response.json()["snapshot"])
        self.assertNotIn(
            "restricted_financial_secret",
            response.json()["snapshot"],
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_http_write_methods_rejected_and_record_unchanged(self):
        self.authenticate(self.comptroller)
        url = f"/api/visible-msrs/{self.msr.pk}/"
        original = dict(self.msr.snapshot)
        original_count = MSR.objects.count()

        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    url,
                    data={"snapshot": {"scope": "UNAUTHORIZED CHANGE"}},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 405)
                self.msr.refresh_from_db()
                self.assertEqual(self.msr.snapshot, original)
                self.assertEqual(MSR.objects.count(), original_count)

    def test_custom_mutation_actions_are_not_routed(self):
        self.authenticate(self.comptroller)
        for action in ("transition", "documents", "signing-reviews"):
            with self.subTest(action=action):
                response = self.client.post(
                    f"/api/visible-msrs/{self.msr.pk}/{action}/",
                    data={},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 404)

    def test_http_roles_receive_exact_commercial_snapshot_fields(self):
        from .services import SNAPSHOT_FIELDS

        for actor in (self.comptroller, self.marketing, self.sales):
            with self.subTest(role=actor.role):
                self.client.logout()
                self.authenticate(actor)
                response = self.client.get(
                    f"/api/visible-msrs/{self.msr.pk}/"
                )
                self.assertEqual(response.status_code, 200)
                snapshot = response.json()["snapshot"]
                self.assertEqual(
                    set(snapshot), {"scope", "total_price"}
                )
                self.assertTrue(set(snapshot) <= SNAPSHOT_FIELDS)
                self.assertNotIn(
                    "restricted_financial_secret", snapshot
                )
