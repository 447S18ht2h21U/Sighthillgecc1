"""Test-only release checks for contractor payment history routing."""

import time

from django.test import override_settings
from django.urls import path

from .own_contractor_payment_api import own_contractor_payment_history
from .test_access_compensation_disclosure import CompensationDisclosureTests


urlpatterns = [
    path(
        "api/own-contractor-payments/",
        own_contractor_payment_history,
        name="step3732-test-contractor-payments",
    ),
]

PATH = "/api/own-contractor-payments/"
PASSWORD = "IsolatedRouting#3732Test"


@override_settings(ROOT_URLCONF=__name__)
class ContractorPaymentRouteReleaseGuardTests(CompensationDisclosureTests):
    def login_actor(self):
        self.user_a.set_password(PASSWORD)
        self.user_a.save(update_fields=["password"])
        self.assertTrue(
            self.client.login(
                username=self.user_a.username,
                password=PASSWORD,
            )
        )
        session = self.client.session
        session["last_activity"] = time.time()
        session.save()

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=False)
    def test_authenticated_get_denied_while_gate_disabled(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_actor()
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(
            str(self.contractor_record_a.pk).encode(),
            response.content,
        )

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_authenticated_post_rejected_even_with_test_gate_enabled(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_actor()
        response = self.client.post(PATH, data={})
        self.assertEqual(response.status_code, 405)
        self.assertNotIn(
            str(self.contractor_record_a.pk).encode(),
            response.content,
        )