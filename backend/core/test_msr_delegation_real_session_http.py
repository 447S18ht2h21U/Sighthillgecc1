"""Real Django session and CSRF integration, with a test-only URL.

No operational delegation endpoint is registered in config.urls.
"""

import time
from uuid import uuid4
from unittest.mock import patch

from django.middleware.csrf import get_token
from django.http import HttpRequest
from django.test import TestCase, Client, override_settings
from django.urls import path

from .models import Role, User
from .msr_delegation_http_prototype import MSRDelegationHTTPPrototype


PATH = "/test-only/msr-delegation-request/"
prototype = MSRDelegationHTTPPrototype.as_view()
urlpatterns = [
    path(
        "test-only/msr-delegation-request/",
        prototype,
        {"action": "request"},
        name="test-only-msr-delegation-request",
    ),
]


@override_settings(ROOT_URLCONF=__name__)
class RealDelegationSessionHTTPTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username="delegation_session_manager_3880",
            password="SyntheticTestOnly#3880Password",
            role=Role.SALES_MANAGER,
            initials="DM",
        )
        self.other = User.objects.create_user(
            username="delegation_session_technician_3880",
            password="SyntheticTestOnly#3880Password",
            role=Role.TECHNICIAN,
            initials="DT",
        )
        self.client = Client(enforce_csrf_checks=True)
        self.payload = {
            "recipient_id": str(uuid4()),
            "source_associate_id": str(uuid4()),
            "project_ids": [str(uuid4())],
            "starts_at": "2026-11-01T10:00:00-04:00",
            "ends_at": "2026-11-03T10:00:00-05:00",
            "reason": "Documented temporary coverage",
        }

    def login(self, actor, *, age=0):
        self.client.force_login(actor)
        session = self.client.session
        session["last_activity"] = time.time() - age
        session.save()

    def csrf(self):
        request = HttpRequest()
        token = get_token(request)
        self.client.cookies["csrftoken"] = request.META["CSRF_COOKIE"]
        return token

    def send(self, *, token=None):
        headers = {}
        if token is not None:
            headers["HTTP_X_CSRFTOKEN"] = token
        return self.client.post(
            PATH,
            self.payload,
            content_type="application/json",
            **headers,
        )

    def test_anonymous_post_denied(self):
        response = self.send()
        self.assertIn(response.status_code, (401, 403))

    def test_missing_csrf_rejected_before_actor_gate(self):
        self.login(self.manager)
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor"
        ) as verified:
            response = self.send()
            self.assertEqual(response.status_code, 403)
            self.assertIn(b"CSRF", response.content)
            verified.assert_not_called()

    def test_invalid_csrf_rejected_before_actor_gate(self):
        self.login(self.manager)
        self.csrf()
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor"
        ) as verified:
            response = self.send(token="invalid")
            self.assertEqual(response.status_code, 403)
            verified.assert_not_called()

    def test_valid_csrf_reaches_guard_but_never_executes(self):
        self.login(self.manager)
        token = self.csrf()
        response = self.send(token=token)
        self.assertEqual(response.status_code, 403)
        self.assertIn(
            b"Operational MSR delegation is not enabled",
            response.content,
        )
        self.assertEqual(
            response["Cache-Control"], "private, no-store"
        )

    def test_wrong_role_denied_before_dispatch(self):
        self.login(self.other)
        token = self.csrf()
        with patch(
            "core.msr_delegation_http_prototype.execute_prepared_delegation_command"
        ) as dispatch:
            response = self.send(token=token)
            self.assertEqual(response.status_code, 403)
            dispatch.assert_not_called()

    def test_deactivated_user_denied(self):
        self.login(self.manager)
        token = self.csrf()
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        response = self.send(token=token)
        self.assertIn(response.status_code, (401, 403))

    def test_expired_session_denied_and_logged_out(self):
        self.login(self.manager, age=1900)
        token = self.csrf()
        response = self.send(token=token)
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_missing_activity_denied(self):
        self.login(self.manager)
        session = self.client.session
        session.pop("last_activity", None)
        session.save()
        token = self.csrf()
        response = self.send(token=token)
        self.assertIn(response.status_code, (401, 403))

    def test_get_is_not_allowed(self):
        self.login(self.manager)
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 405)

    def test_live_route_remains_unregistered(self):
        from django.urls import resolve, Resolver404
        with self.settings(ROOT_URLCONF="config.urls"):
            with self.assertRaises(Resolver404):
                resolve(PATH)


if __name__ == "__main__":
    import unittest
    unittest.main()