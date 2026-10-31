"""Security tests against the registered production URL configuration."""

import time

from django.test import override_settings
from django.urls import resolve, reverse

from .own_contractor_payment_api import own_contractor_payment_history
from .test_access_compensation_disclosure import CompensationDisclosureTests


PATH = "/api/own-contractor-payments/"
PASSWORD = "IsolatedLiveRoute#3736Test"


@override_settings(ROOT_URLCONF="config.urls")
class ContractorLiveRouteSecurityTests(CompensationDisclosureTests):
    def login_actor(self, *, age=0):
        self.user_a.set_password(PASSWORD)
        self.user_a.save(update_fields=["password"])
        self.assertTrue(
            self.client.login(
                username=self.user_a.username,
                password=PASSWORD,
            )
        )
        session = self.client.session
        session["last_activity"] = time.time() - age
        session.save()

    def verify_registered_route(self):
        self.assertIs(
            resolve(PATH).func,
            own_contractor_payment_history,
        )
        self.assertEqual(
            reverse("own-contractor-payments"),
            PATH,
        )

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=False)
    def test_actual_route_denies_authenticated_get(self):
        self.verify_registered_route()
        self._approve_contractor(self.contractor_record_a)
        self.login_actor()

        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(
            str(self.contractor_record_a.pk).encode(),
            response.content,
        )

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_actual_route_remains_read_only(self):
        self.verify_registered_route()
        self._approve_contractor(self.contractor_record_a)
        self.login_actor()

        response = self.client.post(PATH, data={})
        self.assertEqual(response.status_code, 405)
        self.assertNotIn(
            str(self.contractor_record_a.pk).encode(),
            response.content,
        )

    @override_settings(VERIDIAN_OWN_CONTRACTOR_PAYMENT_ROLE_GATE_ENABLED=True)
    def test_actual_route_denies_expired_session(self):
        self.verify_registered_route()
        self._approve_contractor(self.contractor_record_a)
        self.login_actor(age=1900)

        response = self.client.get(PATH)
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(
            str(self.contractor_record_a.pk).encode(),
            response.content,
        )