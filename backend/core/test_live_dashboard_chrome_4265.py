"""Real approved fictional MSR through Django HTTP into Chrome.

Isolated test only. No external delivery or operational database use.
"""
import os
import shutil
import subprocess
import time
from pathlib import Path

from django.conf import settings
from django.test import LiveServerTestCase, override_settings

from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


@override_settings(STATIC_URL="/static/")
class LiveDashboardChrome4265Tests(LiveServerTestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

    def test_actual_approved_msr_renders_in_chrome(self):
        from django.db import connection
        from urllib.parse import parse_qs, urlsplit

        database = connection.settings_dict
        self.assertEqual(
            database["ENGINE"], "django.db.backends.sqlite3"
        )
        name = str(database["NAME"])
        if name != ":memory:":
            parsed = urlsplit(name)
            parameters = parse_qs(parsed.query)
            self.assertEqual(parsed.scheme, "file")
            self.assertTrue(
                parsed.path.startswith("memorydb_"),
                "Expected Django's isolated shared-memory database.",
            )
            self.assertEqual(parameters.get("mode"), ["memory"])
            self.assertEqual(parameters.get("cache"), ["shared"])
        self.assertIsNone(settings.MIGRATION_MODULES["core"])

        self.client.force_login(self.comptroller)
        session = self.client.session
        session["last_activity"] = time.time()
        session.save()

        cookie_name = settings.SESSION_COOKIE_NAME
        cookie = (
            cookie_name + "=" + self.client.cookies[cookie_name].value
        )

        root = Path(__file__).resolve().parents[2]
        frontend = root / "frontend"
        script = frontend / "tests" / "live-dashboard-chrome-4265.mjs"

        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required.")

        env = os.environ.copy()
        env["VERIDIAN_TEST_LIVE_URL"] = self.live_server_url
        env["VERIDIAN_TEST_SESSION_COOKIE"] = cookie
        env["VERIDIAN_TEST_PROJECT_CODE"] = self.project.code

        result = subprocess.run(
            [node, str(script)],
            cwd=str(frontend),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        self.assertEqual(
            result.returncode,
            0,
            "Chrome integration failed:\n"
            + result.stdout[-6000:]
            + "\n"
            + result.stderr[-6000:],
        )
        print(result.stdout)