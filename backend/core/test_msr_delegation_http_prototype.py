"""HTTP behavior tests without URL registration or database connections."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from rest_framework.test import APIRequestFactory, force_authenticate

from core.msr_delegation_http_prototype import (
    MSRDelegationHTTPPrototype,
    prototype_grants_live_msr_access,
)


class DelegationHTTPPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.path = "/unregistered-delegation-test/"
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
        self.view = MSRDelegationHTTPPrototype.as_view()

    def send(self, method="post", data=None, authenticated=True,
             action="request"):
        value = self.payload if data is None else data
        request = getattr(self.factory, method)(
            self.path, value, format="json"
        )
        if authenticated:
            force_authenticate(request, user=self.actor)
        return self.view(request, action=action)

    def test_anonymous_post_denied(self):
        response = self.send(authenticated=False)
        self.assertIn(response.status_code, (401, 403))

    def test_anonymous_request_does_not_prepare(self):
        with patch(
            "core.msr_delegation_http_prototype.prepare_delegation_command"
        ) as prepare:
            response = self.send(authenticated=False)
            self.assertIn(response.status_code, (401, 403))
            prepare.assert_not_called()

    def test_get_method_not_allowed(self):
        response = self.send(method="get")
        self.assertEqual(response.status_code, 405)

    def test_put_method_not_allowed(self):
        response = self.send(method="put")
        self.assertEqual(response.status_code, 405)

    def test_delete_method_not_allowed(self):
        response = self.send(method="delete")
        self.assertEqual(response.status_code, 405)

    def test_valid_request_still_denied(self):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor",
            return_value=SimpleNamespace(pk=self.actor_id),
        ):
            response = self.send()
        self.assertEqual(response.status_code, 403)

    def test_invalid_payload_returns_400(self):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor",
            return_value=SimpleNamespace(pk=self.actor_id),
        ):
            response = self.send(data={
                "manager_id": str(uuid4())
            })
        self.assertEqual(response.status_code, 400)

    def test_unknown_action_denied(self):
        response = self.send(action="unsupported")
        self.assertEqual(response.status_code, 403)

    def test_valid_approval_still_denied(self):
        with patch(
            "core.msr_delegation_api_boundary.verified_delegation_actor",
            return_value=SimpleNamespace(pk=self.actor_id),
        ):
            response = self.send(
                data={"reason": "Independent executive approval"},
                action="approve",
            )
        self.assertEqual(response.status_code, 403)

    def test_response_no_cache(self):
        response = self.send(authenticated=False)
        self.assertEqual(
            response["Cache-Control"], "private, no-store"
        )
        self.assertEqual(
            response["X-Content-Type-Options"], "nosniff"
        )

    def test_no_registered_route(self):
        root = Path(__file__).resolve().parents[1]
        urls = (root / "config" / "urls.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("msr_delegation_http_prototype", urls)
        self.assertNotIn("msr-delegations", urls)

    def test_prototype_cannot_grant_access(self):
        self.assertIs(prototype_grants_live_msr_access(), False)


if __name__ == "__main__":
    unittest.main()