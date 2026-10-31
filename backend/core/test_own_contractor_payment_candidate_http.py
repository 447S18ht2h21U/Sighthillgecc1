"""Candidate authorization over real sessions and real contractor records.

The route is test-only. Patching is restricted to has_permission during each
request; no operational authorization or permission grants are changed.
"""

import time
from unittest.mock import patch

from django.test import override_settings
from django.urls import path

from .access_own_compensation_candidate_permission import (
    candidate_own_compensation_allowed,
)
from .own_contractor_payment_api import own_contractor_payment_history
from .test_access_compensation_disclosure import CompensationDisclosureTests


urlpatterns = [
    path(
        "test-only/candidate-payment-history/",
        own_contractor_payment_history,
        name="test-only-candidate-payment-history",
    )
]

PATH = "/test-only/candidate-payment-history/"
PASSWORD = "CandidateSession#3712TestPassword"


@override_settings(ROOT_URLCONF=__name__)
class CandidatePaymentHTTPTests(CompensationDisclosureTests):
    def login_as(self, actor, *, age=0):
        actor.set_password(PASSWORD)
        actor.save(update_fields=["password"])
        self.assertTrue(
            self.client.login(username=actor.username, password=PASSWORD)
        )
        session = self.client.session
        session["last_activity"] = time.time() - age
        session.save()

    def candidate_request(self):
        with patch(
            "core.access_compensation_report_permissions.has_permission",
            side_effect=candidate_own_compensation_allowed,
        ) as checker:
            response = self.client.get(PATH)
        return response, checker

    def test_candidate_shows_own_approved_record_only(self):
        self._approve_contractor(self.contractor_record_a)
        self._approve_contractor(self.contractor_record_b)
        self.login_as(self.user_a)

        response, checker = self.candidate_request()
        self.assertEqual(response.status_code, 200)

        results = response.json()["results"]
        self.assertEqual(
            {item["record_id"] for item in results},
            {str(self.contractor_record_a.pk)},
        )
        self.assertEqual(results[0]["status"], "APPROVED")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        checker.assert_called_once()
        self.assertEqual(checker.call_args.args[1], "compensation.own.view")

    def test_candidate_does_not_show_draft_records(self):
        self.login_as(self.user_a)
        response, checker = self.candidate_request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        checker.assert_called_once()

    def test_candidate_rejects_unrecognized_stored_role(self):
        self.login_as(self.user_a)
        self.user_a.role = "UNKNOWN_ROLE"
        self.user_a.save(update_fields=["role"])
        response, checker = self.candidate_request()
        self.assertEqual(response.status_code, 403)
        checker.assert_called_once()

    def test_candidate_cannot_override_expired_session(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_as(self.user_a, age=1900)
        response, checker = self.candidate_request()
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(b"500.00", response.content)
        checker.assert_not_called()