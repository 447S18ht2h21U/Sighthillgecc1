"""Real HTTP integration smoke tests on Django's isolated SQLite live server."""

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.test import LiveServerTestCase, override_settings

from .models import Customer, MSR, Project, Role, User


import threading

from django.core.servers.basehttp import ThreadedWSGIServer
from django.test.testcases import LiveServerThread


class _SerialSQLiteWSGIServer(ThreadedWSGIServer):
    """Test only: allow one WSGI request at a time on shared SQLite."""

    def __init__(self, *args, **kwargs):
        self._sqlite_request_lock = threading.RLock()
        super().__init__(*args, **kwargs)

    def process_request_thread(self, request, client_address):
        with self._sqlite_request_lock:
            return super().process_request_thread(request, client_address)


class _SerialSQLiteLiveServerThread(LiveServerThread):
    server_class = _SerialSQLiteWSGIServer

@override_settings(STATIC_URL="/static/", MEDIA_URL="/media/", DEBUG=True)
class VisibleMSRLiveHTTPSmokeTests(LiveServerTestCase):
    host = "127.0.0.1"
    server_thread_class = _SerialSQLiteLiveServerThread

    @classmethod
    def setUpClass(cls):
        database = settings.DATABASES["default"]
        allowed_names = {
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        }
        if (
            database["ENGINE"] != "django.db.backends.sqlite3"
            or str(database["NAME"]) not in allowed_names
        ):
            raise RuntimeError("SAFETY STOP: Live test requires in-memory SQLite.")
        super().setUpClass()



    def setUp(self):
        self.password = "IsolatedHTTP2026!Test"
        self.comptroller = self.user("http_controller", Role.COMPTROLLER)
        self.sales = self.user("http_sales", Role.SALES_ASSOCIATE)
        self.other_sales = self.user("http_other_sales", Role.SALES_ASSOCIATE)
        self.dba = self.user("http_dba", Role.DATABASE_ADMINISTRATOR)
        self.ceo = self.user("http_ceo", Role.CEO)
        self.sales_manager = self.user("http_sales_manager", Role.SALES_MANAGER)
        self.installation_manager = self.user(
            "http_installation_manager", Role.INSTALLATION_MANAGER
        )
        self.technician = self.user("http_technician", Role.TECHNICIAN)
        self.ap = self.user(
            "http_accounts_payable", Role.ACCOUNTS_PAYABLE_ASSOCIATE
        )
        self.marketing = self.user("http_marketing", Role.MARKETING)

        customer = Customer.objects.create(
            legal_name="Isolated HTTP Test Customer",
            billing_address="1 Synthetic Test Street",
            created_by=self.comptroller,
        )

        self.own_msr = self.record(
            customer, self.sales, "HTTP-ISOLATED-001", "Owned HTTP record"
        )
        self.other_msr = self.record(
            customer, self.other_sales, "HTTP-ISOLATED-002",
            "Other HTTP record"
        )

        host = urllib.parse.urlsplit(self.live_server_url).hostname
        if host not in ("127.0.0.1", "localhost"):
            raise RuntimeError("SAFETY STOP: Non-loopback live server refused.")

    def user(self, username, role):
        return User.objects.create_user(
            username=username,
            password=self.password,
            role=role,
        )

    def record(self, customer, associate, code, name):
        project = Project.objects.create(
            code=code,
            customer=customer,
            location="Synthetic test location",
            sales_associate=associate,
            reviewer=self.comptroller,
        )
        return MSR.objects.create(
            project=project,
            number=1,
            created_by=associate,
            prepared_by=associate,
            snapshot={"customer": name, "scope": "Synthetic HTTP work"},
        )

    def request(self, opener, path, method="GET", payload=None, csrf=None):
        if not path.startswith("/api/"):
            raise RuntimeError("SAFETY STOP: Unexpected HTTP path.")

        headers = {}
        data = None

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if csrf is not None:
            headers["X-CSRFToken"] = csrf

        req = urllib.request.Request(
            self.live_server_url + path,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            response = opener.open(req, timeout=12)
        except urllib.error.HTTPError as exc:
            response = exc

        with response:
            status = response.status
            body = response.read()
            content_type = response.headers.get("Content-Type", "")

        if "application/json" not in content_type.lower():
            raise AssertionError(
                f"Expected JSON from {path}; HTTP status {status}."
            )

        return status, json.loads(body)

    def login(self, username):
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

        status, csrf_response = self.request(opener, "/api/csrf/")
        self.assertEqual(status, 200)
        token = csrf_response["csrfToken"]

        status, body = self.request(
            opener,
            "/api/dev-login/",
            method="POST",
            payload={"username": username, "password": self.password},
            csrf=token,
        )
        if status != 200:
            from django.conf import settings
            from django.urls import resolve
            route = resolve("/api/dev-login/")
            print("LIVE LOGIN DIAGNOSTIC STATUS:", status, flush=True)
            print("LIVE LOGIN DIAGNOSTIC DETAIL:",
                  body.get("detail", "<no detail>") if isinstance(body, dict)
                  else "<non-object JSON>", flush=True)
            print("LIVE LOGIN DIAGNOSTIC ENVIRONMENT:",
                  settings.ENVIRONMENT, flush=True)
            print("LIVE LOGIN DIAGNOSTIC DEBUG:",
                  settings.DEBUG, flush=True)
            print("LIVE LOGIN DIAGNOSTIC ROUTE:",
                  route.func.__module__ + "." + route.func.__name__,
                  flush=True)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

        # Django rotates the CSRF secret after a successful login.
        # Fetch the new token using the authenticated session.
        csrf_status, csrf_response = self.request(opener, "/api/csrf/")
        self.assertEqual(csrf_status, 200)
        token = csrf_response["csrfToken"]

        return opener, token

    def scenario_comptroller_real_login_and_msr_list(self):
        opener, token = self.login(self.comptroller.username)

        status, actor = self.request(opener, "/api/me/")
        self.assertEqual(status, 200)
        self.assertEqual(actor["role"], Role.COMPTROLLER)

        status, body = self.request(opener, "/api/visible-msrs/")
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 2)

        ids = {str(item["id"]) for item in body["results"]}
        self.assertEqual(
            ids, {str(self.own_msr.pk), str(self.other_msr.pk)}
        )

        status, activity = self.request(
            opener, "/api/activity/", "POST", {}, token
        )
        self.assertEqual(status, 200)
        self.assertTrue(activity["ok"])

    def scenario_sales_session_cannot_view_other_project(self):
        opener, _ = self.login(self.sales.username)

        status, body = self.request(opener, "/api/visible-msrs/")
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 1)
        self.assertEqual(
            str(body["results"][0]["id"]), str(self.own_msr.pk)
        )

        status, _ = self.request(
            opener, f"/api/visible-msrs/{self.other_msr.pk}/"
        )
        self.assertEqual(status, 404)

    def scenario_unauthorized_session_denied(self):
        opener, _ = self.login(self.dba.username)
        status, _ = self.request(opener, "/api/visible-msrs/")
        self.assertEqual(status, 403)

    def scenario_anonymous_session_denied(self):
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        status, _ = self.request(opener, "/api/visible-msrs/")
        self.assertIn(status, (401, 403))

    def scenario_direct_marketing_http_security(self):
        """Verify real sessions cannot bypass Marketing route permissions."""
        marketing, _ = self.login(self.marketing.username)

        status, body = self.request(marketing, "/api/marketing-msrs/")
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 2)
        self.assertEqual(
            {str(item["id"]) for item in body["results"]},
            {str(self.own_msr.pk), str(self.other_msr.pk)},
        )

        status, detail = self.request(
            marketing, f"/api/marketing-msrs/{self.other_msr.pk}/"
        )
        self.assertEqual(status, 200)
        self.assertEqual(str(detail["id"]), str(self.other_msr.pk))

        for username in (
            self.sales.username,
            self.dba.username,
            self.ap.username,
        ):
            opener, _ = self.login(username)
            status, _ = self.request(opener, "/api/marketing-msrs/")
            self.assertEqual(
                status, 403,
                f"Marketing list incorrectly accessible to {username}.",
            )
            status, _ = self.request(
                opener, f"/api/marketing-msrs/{self.own_msr.pk}/"
            )
            self.assertEqual(
                status, 403,
                f"Marketing detail incorrectly accessible to {username}.",
            )

        for username in (self.dba.username, self.ap.username):
            opener, _ = self.login(username)
            status, _ = self.request(opener, "/api/visible-msrs/")
            self.assertEqual(
                status, 403,
                f"Visible MSR list incorrectly accessible to {username}.",
            )

        print("DIRECT HTTP: Marketing list and detail authorized", flush=True)
        print("DIRECT HTTP: Non-Marketing list and detail denied", flush=True)
        print("DIRECT HTTP: DBA and Accounts Payable visible list denied", flush=True)

    def scenario_existing_sessions_recheck_current_access(self):
        """A signed-in session never preserves obsolete MSR authority."""

        manager_session, _ = self.login(self.sales_manager.username)
        marketing_session, _ = self.login(self.marketing.username)

        status, manager_records = self.request(
            manager_session, "/api/visible-msrs/"
        )
        self.assertEqual(status, 200)
        self.assertEqual(manager_records["count"], 2)

        status, marketing_records = self.request(
            marketing_session, "/api/marketing-msrs/"
        )
        self.assertEqual(status, 200)
        self.assertEqual(marketing_records["count"], 2)

        # Simulate external changes after both sessions are authenticated.
        # Only disposable synthetic test accounts are modified.
        manager_updated = User.objects.filter(
            pk=self.sales_manager.pk,
            role=Role.SALES_MANAGER,
            is_active=True,
        ).update(role=Role.DATABASE_ADMINISTRATOR)
        self.assertEqual(manager_updated, 1)

        marketing_updated = User.objects.filter(
            pk=self.marketing.pk,
            role=Role.MARKETING,
            is_active=True,
        ).update(is_active=False)
        self.assertEqual(marketing_updated, 1)

        status, _ = self.request(manager_session, "/api/visible-msrs/")
        self.assertIn(status, (401, 403))
        status, _ = self.request(
            manager_session, f"/api/visible-msrs/{self.own_msr.pk}/"
        )
        self.assertIn(status, (401, 403))

        status, _ = self.request(marketing_session, "/api/marketing-msrs/")
        self.assertIn(status, (401, 403))
        status, _ = self.request(
            marketing_session, f"/api/marketing-msrs/{self.other_msr.pk}/"
        )
        self.assertIn(status, (401, 403))

        self.sales_manager.refresh_from_db()
        self.marketing.refresh_from_db()
        self.assertEqual(
            self.sales_manager.role, Role.DATABASE_ADMINISTRATOR
        )
        self.assertFalse(self.marketing.is_active)

        print("LIVE SESSION: Role downgrade immediately denied", flush=True)
        print("LIVE SESSION: Disabled Marketing account denied", flush=True)
        print("LIVE SESSION: Original authenticated sessions reused", flush=True)

    def _fixture_teardown(self):
        """Only skip flush for this one disposable in-memory test database."""
        from django.db import connections

        database = connections["default"]
        allowed_names = {
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        }
        if (
            database.vendor != "sqlite"
            or str(database.settings_dict["NAME"]) not in allowed_names
        ):
            raise RuntimeError(
                "SAFETY STOP: Refusing to skip teardown outside test memory."
            )
        # This test runs once. The Django runner destroys the entire
        # disposable test database instead of deleting immutable MSRs.
        # No application triggers, constraints, or migrations are changed.

    def test_all_real_http_security_scenarios(self):
        """Exercise separate browser-style sessions against the real API."""
        self.scenario_anonymous_session_denied()
        self.scenario_comptroller_real_login_and_msr_list()
        self.scenario_sales_session_cannot_view_other_project()
        self.scenario_unauthorized_session_denied()
        self.scenario_direct_marketing_http_security()

        # Exercise actual Chrome and React against this disposable live server.
        import hashlib
        import os
        from pathlib import Path
        import shutil
        import subprocess

        from django.db import connections

        database = connections["default"]
        if (
            database.vendor != "sqlite"
            or str(database.settings_dict["NAME"])
            != "file:memorydb_default?mode=memory&cache=shared"
        ):
            raise RuntimeError(
                "SAFETY STOP: Browser integration requires Django test memory."
            )

        root = Path(__file__).resolve().parents[2]
        frontend = root / "frontend"
        runner = frontend / "tests" / "visible-msr" / "live-browser-runner.mjs"
        approved_hash = (
            "CCB56B7E99B9FE3B0B276181CC6970E1"
            "25889018AFE4E9378E4633A352CB4931"
        )

        if hashlib.sha256(runner.read_bytes()).hexdigest().upper() != approved_hash:
            raise RuntimeError("SAFETY STOP: Browser runner hash mismatch.")

        node = shutil.which("node.exe")
        if node is None:
            raise RuntimeError("SAFETY STOP: Node.js unavailable.")

        if not self.live_server_url.startswith("http://127.0.0.1:"):
            raise RuntimeError("SAFETY STOP: Non-loopback Django server.")

        child_env = os.environ.copy()
        for key in list(child_env):
            if key.startswith("PG") or key == "DATABASE_URL":
                child_env.pop(key, None)

        child_env.update({
            "VERIDIAN_ISOLATED_BROWSER_RUN": "DJANGO_LIVE_TEST_SQLITE_MEMORY",
            "VERIDIAN_ISOLATED_DJANGO_URL": self.live_server_url,
            "VERIDIAN_ISOLATED_BROWSER_PASSWORD": self.password,
        })

        print("=== REAL CHROME / REACT / DJANGO INTEGRATION ===", flush=True)

        try:
            result = subprocess.run(
                [node, str(runner)],
                cwd=str(frontend),
                env=child_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise AssertionError(
                "Browser integration exceeded its 120-second safety limit."
            ) from error

        if result.stdout:
            print(result.stdout, flush=True)

        if result.stderr:
            print(result.stderr, flush=True)

        self.assertEqual(
            result.returncode, 0,
            "Real Chrome/React/Django integration failed."
        )
        self.scenario_existing_sessions_recheck_current_access()