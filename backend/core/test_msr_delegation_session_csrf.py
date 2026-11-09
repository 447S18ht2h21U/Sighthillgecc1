"""Authentication and CSRF checks against the unregistered HTTP prototype.

Simulated authenticated sessions, real DRF authentication/CSRF logic.
No force_authenticate, database, migrations, or operational URL registration.
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.middleware.csrf import get_token
from rest_framework.test import APIRequestFactory

from core.msr_delegation_http_prototype import MSRDelegationHTTPPrototype


class DelegationSessionCSRFSecurityTests(unittest.TestCase):

    def setUp(self):
        self.factory = APIRequestFactory(enforce_csrf_checks=True)
        self.view = MSRDelegationHTTPPrototype.as_view()
        self.actor_id = uuid4()
        self.actor = SimpleNamespace(
            pk=self.actor_id,
            is_authenticated=True,
            is_active=True,
        )
        self.payload = {
            "recipient_id": str(uuid4()),
            "source_associate_id": str(uuid4()),
            "project_ids": [str(uuid4())],
            "starts_at": "2026-11-01T10:00:00-04:00",
            "ends_at": "2026-11-03T10:00:00-05:00",
            "reason": "Documented temporary coverage",
        }

    def make_request(self, *, csrf=False, invalid_csrf=False,
                     anonymous=False, age=0, method="post"):
        request = getattr(self.factory, method)(
            "/unregistered-delegation-security/",
            self.payload,
            format="json",
        )
        request.user = AnonymousUser() if anonymous else self.actor
        request.session = {
            "last_activity": time.time() - age,
        }

        if csrf:
            token = get_token(request)
            # Supply the cookie paired with the generated CSRF header.
            # DRF CSRFCheck reads the cookie from request.COOKIES.
            request.COOKIES["csrftoken"] = request.META["CSRF_COOKIE"]
            request.META["HTTP_X_CSRFTOKEN"] = (
                "invalid" if invalid_csrf else token
            )

        return request

    def send(self, request, action="request"):
        return self.view(request, action=action)

    def test_anonymous_post_denied(self):
        response = self.send(
            self.make_request(anonymous=True)
        )
        self.assertIn(response.status_code, (401, 403))

    def test_authenticated_post_without_csrf_denied(self):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor"
        ) as verify:
            response = self.send(self.make_request())
            self.assertEqual(response.status_code, 403)
            self.assertIn(b"CSRF", response.render().content)
            verify.assert_not_called()

    def test_authenticated_post_with_invalid_csrf_denied(self):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor"
        ) as verify:
            response = self.send(
                self.make_request(csrf=True, invalid_csrf=True)
            )
            self.assertEqual(response.status_code, 403)
            self.assertIn(b"CSRF", response.render().content)
            verify.assert_not_called()

    def test_valid_csrf_reaches_boundary_but_not_dispatch(self):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor",
            return_value=SimpleNamespace(pk=self.actor_id),
        ) as verify:
            response = self.send(
                self.make_request(csrf=True)
            )
            self.assertEqual(response.status_code, 403)
            self.assertIn(
                b"Operational MSR delegation is not enabled",
                response.render().content,
            )
            verify.assert_called_once()

    def test_expired_session_denied_before_boundary(self):
        with patch("core.auth.logout") as logout:
            with patch(
                "core.msr_delegation_api_boundary.verified_delegation_actor"
            ) as verify:
                response = self.send(
                    self.make_request(csrf=True, age=1900)
                )
                self.assertIn(response.status_code, (401, 403))
                self.assertIn(
                    b"Session expired",
                    response.render().content,
                )
                logout.assert_called_once()
                verify.assert_not_called()

    def test_missing_last_activity_denied(self):
        request = self.make_request(csrf=True)
        request.session.clear()
        with patch("core.auth.logout") as logout:
            response = self.send(request)
            self.assertIn(response.status_code, (401, 403))
            logout.assert_called_once()

    def test_get_method_not_allowed(self):
        response = self.send(
            self.make_request(csrf=True, method="get")
        )
        self.assertEqual(response.status_code, 405)

    def test_unauthenticated_request_never_prepares_command(self):
        with patch(
            "core.msr_delegation_http_prototype.prepare_delegation_command"
        ) as prepare:
            self.send(self.make_request(anonymous=True))
            prepare.assert_not_called()

    def test_csrf_denial_never_executes_dispatch(self):
        with patch(
            "core.msr_delegation_http_prototype.execute_prepared_delegation_command"
        ) as execute:
            response = self.send(self.make_request())
            self.assertEqual(response.status_code, 403)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()