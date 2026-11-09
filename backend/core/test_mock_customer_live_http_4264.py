"""Real HTTP dashboard acceptance with a disposable Django live test server.

No persistent database, external signing, or customer delivery is used.
"""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.test import LiveServerTestCase, override_settings

from .models import Role, User
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


@override_settings(STATIC_URL="/static/")
class MockCustomerLiveHTTP4264Tests(LiveServerTestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def actual_http_response(self, actor=None):
        cookie = ""
        if actor is not None:
            self.client.force_login(actor)
            session = self.client.session
            session["last_activity"] = time.time()
            session.save()
            session_name = "sessionid"
            from django.conf import settings
            session_name = settings.SESSION_COOKIE_NAME
            cookie = (
                session_name + "=" +
                self.client.cookies[session_name].value
            )

        headers = {"Accept": "application/json"}
        if cookie:
            headers["Cookie"] = cookie

        request = Request(
            self.live_server_url + "/api/project-dashboard/",
            headers=headers,
            method="GET",
        )

        try:
            with urlopen(request, timeout=15) as response:
                return (
                    response.status,
                    dict(response.headers.items()),
                    json.loads(response.read().decode("utf-8")),
                )
        except HTTPError as error:
            return error.code, dict(error.headers.items()), None

    @staticmethod
    def entries(data):
        rows = list(data.get("needs_attention", []))
        for stage in data.get("stages", []):
            rows.extend(stage.get("projects", []))
        return rows

    def test_anonymous_http_dashboard_is_denied(self):
        status, _, _ = self.actual_http_response()
        self.assertIn(status, (401, 403))

    def test_comptroller_session_sees_real_approved_msr(self):
        status, headers, data = self.actual_http_response(
            self.comptroller
        )
        self.assertEqual(status, 200)

        cache = headers.get("Cache-Control", "")
        self.assertIn("no-store", cache.lower())

        rows = [
            item for item in self.entries(data)
            if str(item["id"]) == str(self.project.pk)
        ]
        self.assertTrue(rows, "Approved fictional project must appear.")

        for item in rows:
            self.assertEqual(item["code"], self.project.code)
            evidence = item["workflow_evidence"]
            self.assertTrue(evidence["read_only"])
            self.assertEqual(
                evidence["statuses"]["approved_msr"], "VERIFIED"
            )
            self.assertEqual(
                evidence["statuses"]["receipt_delivery"],
                "NOT_EVALUATED",
            )
            self.assertEqual(
                evidence["statuses"]["completed_docusign"],
                "NOT_EVALUATED",
            )
            self.assertEqual(
                evidence["statuses"]["project_completion"],
                "BLOCKED",
            )
            self.assertFalse(
                evidence["installation_authorized"]
            )
            self.assertFalse(
                evidence["project_completion_authorized"]
            )

    def test_other_sales_associate_cannot_see_project_over_http(self):
        other = User.objects.create_user(
            username="live4264_other",
            password="synthetic-test-only",
            role=Role.SALES_ASSOCIATE,
            initials="LX",
        )
        status, _, data = self.actual_http_response(other)
        self.assertEqual(status, 200)

        identifiers = {
            str(item["id"]) for item in self.entries(data)
        }
        self.assertNotIn(str(self.project.pk), identifiers)