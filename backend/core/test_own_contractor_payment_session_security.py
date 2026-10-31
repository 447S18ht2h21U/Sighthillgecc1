"""Real session authentication tests with a private, test-only URL.

The central permission evaluator is never mocked or enabled here.
"""

import time
import uuid

from django.test import TestCase, override_settings
from django.urls import path

from .models import Role, User
from .own_contractor_payment_api import own_contractor_payment_history


urlpatterns = [
    path(
        "test-only/own-contractor-payments/",
        own_contractor_payment_history,
        name="test-only-own-contractor-payments",
    ),
]

PATH = "/test-only/own-contractor-payments/"
PASSWORD = "SessionOnlyTest#3705Password"


@override_settings(ROOT_URLCONF=__name__)
class ContractorPaymentSessionSecurityTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="payment_session_test_3705",
            password=PASSWORD,
            role=Role.TECHNICIAN,
            initials="ST",
        )

    def login_with_activity(self, last_activity=None):
        self.assertTrue(
            self.client.login(
                username=self.actor.username,
                password=PASSWORD,
            )
        )
        session = self.client.session
        session["last_activity"] = (
            time.time() if last_activity is None else last_activity
        )
        session.save()

    def assert_denied(self, response):
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn(b"final_amount", response.content)
        self.assertNotIn(b"basis_amount", response.content)

    def test_anonymous_request_is_denied(self):
        self.assert_denied(self.client.get(PATH))

    def test_real_login_is_still_denied_by_permission_gate(self):
        self.login_with_activity()
        self.assert_denied(self.client.get(PATH))

    def test_idle_session_expires_before_permission_evaluation(self):
        self.login_with_activity(time.time() - 1900)
        response = self.client.get(PATH)
        self.assert_denied(response)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deactivated_account_cannot_use_old_session(self):
        self.login_with_activity()
        stored = User.objects.get(pk=self.actor.pk)
        stored.is_active = False
        stored.session_security_token = uuid.uuid4()
        stored.save(update_fields=[
            "is_active",
            "session_security_token",
        ])
        self.assert_denied(self.client.get(PATH))

    def test_rotated_session_security_token_invalidates_session(self):
        self.login_with_activity()
        stored = User.objects.get(pk=self.actor.pk)
        stored.session_security_token = uuid.uuid4()
        stored.save(update_fields=["session_security_token"])
        self.assert_denied(self.client.get(PATH))

    def test_password_change_invalidates_old_session(self):
        self.login_with_activity()
        stored = User.objects.get(pk=self.actor.pk)
        stored.set_password("ChangedOnlyForTest#3705Password")
        stored.save(update_fields=["password"])
        self.assert_denied(self.client.get(PATH))