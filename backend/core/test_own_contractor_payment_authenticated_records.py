"""Test real session identity and real payment ownership together.

The URL exists only in this test module. Permission success is simulated
inside each relevant test; operational permissions remain default-deny.
"""

import time
from unittest.mock import patch

from django.test import override_settings
from django.urls import path

from .own_contractor_payment_api import own_contractor_payment_history
from .test_access_compensation_disclosure import CompensationDisclosureTests


urlpatterns = [
    path(
        "test-only/contractor-payment-records/",
        own_contractor_payment_history,
        name="test-only-contractor-payment-records",
    ),
]

PATH = "/test-only/contractor-payment-records/"
PASSWORD = "IsolatedSession#3706TestPassword"


@override_settings(ROOT_URLCONF=__name__)
class AuthenticatedPaymentRecordTests(CompensationDisclosureTests):
    """Reuse genuine contractor, plan, and payment fixtures."""

    def login_as(self, actor, *, activity_age=0):
        actor.set_password(PASSWORD)
        actor.save(update_fields=["password"])
        self.assertTrue(
            self.client.login(
                username=actor.username,
                password=PASSWORD,
            )
        )
        session = self.client.session
        session["last_activity"] = time.time() - activity_age
        session.save()

    def test_logged_in_contractor_only_sees_own_approved_record(self):
        self._approve_contractor(self.contractor_record_a)
        self._approve_contractor(self.contractor_record_b)
        self.login_as(self.user_a)

        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ) as permitted:
            response = self.client.get(PATH)

        self.assertEqual(response.status_code, 200)
        records = response.json()["results"]
        self.assertEqual(
            {item["record_id"] for item in records},
            {str(self.contractor_record_a.pk)},
        )
        self.assertEqual(records[0]["status"], "APPROVED")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        permitted.assert_called_once()

    def test_logged_in_contractor_cannot_see_draft(self):
        self.login_as(self.user_a)

        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ):
            response = self.client.get(PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_expired_session_cannot_use_simulated_permission(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_as(self.user_a, activity_age=1900)

        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ) as permitted:
            response = self.client.get(PATH)

        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(b"500.00", response.content)
        self.assertNotIn("_auth_user_id", self.client.session)
        permitted.assert_not_called()

    def test_inactive_account_cannot_use_simulated_permission(self):
        self._approve_contractor(self.contractor_record_a)
        self.login_as(self.user_a)

        self.user_a.is_active = False
        self.user_a.save(update_fields=["is_active"])

        with patch(
            "core.access_compensation_report_permissions.has_permission",
            return_value=True,
        ) as permitted:
            response = self.client.get(PATH)

        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(b"500.00", response.content)
        permitted.assert_not_called()