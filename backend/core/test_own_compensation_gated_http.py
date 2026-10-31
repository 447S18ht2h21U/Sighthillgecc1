"""Real-session HTTP tests for the actual disabled-by-default permission service.

Uses a test-only URL and Django override_settings. Does not patch
has_permission or register a production route.
"""

import time

from django.test import override_settings
from django.urls import path

from .own_contractor_payment_api import own_contractor_payment_history
from .test_access_compensation_disclosure import CompensationDisclosureTests


urlpatterns = [
    path(
        "test-only/gated-contractor-payments/",
        own_contractor_payment_history,
        name="test-only-gated-contractor-payments",
    )
]

PATH = "/test-only/gated-contractor-payments/"
PASSWORD = "GatedHTTP#3718TemporaryPassword"


@override_settings(ROOT_URLCONF=__name__)
class GatedContractorPaymentHTTPTests(CompensationDisclosureTests):
    def login_as(self, actor, *, age=0):
        actor.set_password(PASSWORD)
        actor.save(update_fields=["password"])
        self.assertTrue(
            self.client.login(username=actor.username, password=PASSWORD)
        )
        session = self.client.session
        session["last_activity"] = time.time() - age
        session.save()

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=False)
    def test_explicitly_disabled_gate_denies_valid_session(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_as(self.user_a)
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(str(self.contractor_record_a.pk).encode(), response.content)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_test_enabled_gate_returns_only_own_approved_record(self):
        self._approve_contractor(self.contractor_record_a)
        self._approve_contractor(self.contractor_record_b)
        self.login_as(self.user_a)

        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]

        self.assertEqual(
            {item["record_id"] for item in results},
            {str(self.contractor_record_a.pk)},
        )
        self.assertEqual(results[0]["status"], "APPROVED")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_test_enabled_gate_suppresses_draft(self):
        self.login_as(self.user_a)
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_test_enabled_gate_denies_invalid_stored_role(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_as(self.user_a)
        self.user_a.role = "INVALID_ROLE"
        self.user_a.save(update_fields=["role"])

        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(str(self.contractor_record_a.pk).encode(), response.content)

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_test_enabled_gate_cannot_override_expired_session(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_as(self.user_a, age=1900)

        response = self.client.get(PATH)
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(str(self.contractor_record_a.pk).encode(), response.content)