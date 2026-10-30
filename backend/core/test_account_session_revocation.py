from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import AuditEvent, Role, User


@override_settings(DEBUG=True, ENVIRONMENT="development")
class AccountSessionRevocationTests(TestCase):
    """Verify account lifecycle rules using genuine Django sessions."""

    def setUp(self):
        self.password = "SyntheticSessionTest2026!"
        self.comptroller = User.objects.create_user(
            username="synthetic_controller",
            password=self.password,
            role=Role.COMPTROLLER,
            initials="SC",
            email="controller@example.invalid",
        )
        self.associate = User.objects.create_user(
            username="synthetic_associate",
            password=self.password,
            role=Role.SALES_ASSOCIATE,
            initials="SA",
            email="associate@example.invalid",
        )
        self.admin = APIClient()
        self.browser_a = APIClient()
        self.browser_b = APIClient()

    def sign_in(self, client, username):
        response = client.post(
            "/api/dev-login/",
            {"username": username, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def change_active_state(self, active):
        url = f"/api/accounts/{self.associate.pk}/"
        detail = self.admin.get(url)
        self.assertEqual(detail.status_code, 200)
        response = self.admin.patch(
            url,
            {
                "expected_revision": detail.data["revision"],
                "change_note": "Synthetic session revocation regression.",
                "is_active": active,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.associate.refresh_from_db()
        self.assertEqual(self.associate.is_active, active)

    def assert_access(self, client):
        response = client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.associate.pk))

    def assert_denied(self, client):
        response = client.get("/api/me/")
        self.assertIn(response.status_code, (401, 403))

    def test_old_sessions_never_revive_after_reactivation(self):
        self.sign_in(self.admin, self.comptroller.username)
        self.sign_in(self.browser_a, self.associate.username)
        self.sign_in(self.browser_b, self.associate.username)

        self.assert_access(self.browser_a)
        self.assert_access(self.browser_b)

        self.change_active_state(False)
        self.assert_denied(self.browser_a)
        self.assert_denied(self.browser_b)

        self.change_active_state(True)

        # Existing sessions must remain invalid after reactivation.
        self.assert_denied(self.browser_a)
        self.assert_denied(self.browser_b)

        fresh_browser = APIClient()
        self.sign_in(fresh_browser, self.associate.username)
        self.assert_access(fresh_browser)

        events = list(
            AuditEvent.objects.filter(
                action="account.updated",
                entity_id=self.associate.pk,
            ).order_by("sequence")
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(
            [event.payload["after"]["is_active"] for event in events],
            [False, True],
        )
        self.assertTrue(
            all(event.actor_id == self.comptroller.pk for event in events)
        )

    def test_reactivation_before_any_old_session_request(self):
        self.sign_in(self.admin, self.comptroller.username)
        self.sign_in(self.browser_a, self.associate.username)
        self.sign_in(self.browser_b, self.associate.username)

        self.assert_access(self.browser_a)
        self.assert_access(self.browser_b)

        # Neither browser makes a request while the account is inactive.
        self.change_active_state(False)
        self.change_active_state(True)

        # Previously authenticated sessions must remain invalid.
        self.assert_denied(self.browser_a)
        self.assert_denied(self.browser_b)

        fresh_browser = APIClient()
        self.sign_in(fresh_browser, self.associate.username)
        self.assert_access(fresh_browser)

    def test_failed_deactivation_audit_preserves_session_and_token(self):
        from unittest.mock import patch

        self.sign_in(self.admin, self.comptroller.username)
        self.sign_in(self.browser_a, self.associate.username)
        self.assert_access(self.browser_a)

        original_token = self.associate.session_security_token

        url = f"/api/accounts/{self.associate.pk}/"
        detail = self.admin.get(url)
        self.assertEqual(detail.status_code, 200)

        self.admin.raise_request_exception = False

        with patch(
            "core.api.audit",
            side_effect=RuntimeError("synthetic audit failure"),
        ):
            response = self.admin.patch(
                url,
                {
                    "expected_revision": detail.data["revision"],
                    "change_note": "Synthetic audit rollback verification.",
                    "is_active": False,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 500)

        self.associate.refresh_from_db()
        self.assertTrue(self.associate.is_active)
        self.assertEqual(
            self.associate.session_security_token,
            original_token,
        )

        self.assert_access(self.browser_a)

    def test_session_tokens_unique_and_null_updates_rejected(self):
        from django.db import IntegrityError, connection, transaction

        self.assertIsNotNone(self.comptroller.session_security_token)
        self.assertIsNotNone(self.associate.session_security_token)
        self.assertNotEqual(
            self.comptroller.session_security_token,
            self.associate.session_security_token,
        )

        if connection.vendor != "sqlite":
            self.skipTest("SQLite trigger-specific integrity test.")

        original_token = self.associate.session_security_token

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(
                    pk=self.associate.pk
                ).update(session_security_token=None)

        self.associate.refresh_from_db()
        self.assertEqual(
            self.associate.session_security_token,
            original_token,
        )

    def test_password_change_invalidates_existing_session(self):
        self.sign_in(self.admin, self.comptroller.username)
        self.sign_in(self.browser_a, self.associate.username)
        self.assert_access(self.browser_a)

        url = f"/api/accounts/{self.associate.pk}/"
        detail = self.admin.get(url)
        self.assertEqual(detail.status_code, 200)

        new_password = "SyntheticNewPassword2026!Strong"

        response = self.admin.patch(
            url,
            {
                "expected_revision": detail.data["revision"],
                "change_note": "Synthetic password reset verification.",
                "password": new_password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        # The old authenticated session must not survive a password change.
        self.assert_denied(self.browser_a)

        # A fresh login with the new password must succeed.
        fresh_browser = APIClient()
        response = fresh_browser.post(
            "/api/dev-login/",
            {
                "username": self.associate.username,
                "password": new_password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assert_access(fresh_browser)

    def test_fallback_secret_cannot_revive_revoked_session(self):
        from django.conf import settings
        from django.test import override_settings

        old_secret = settings.SECRET_KEY
        new_secret = "SyntheticRotatedSecretForSessionRegression2026!"

        self.sign_in(self.admin, self.comptroller.username)
        self.sign_in(self.browser_a, self.associate.username)
        self.assert_access(self.browser_a)

        # Deactivation rotates the private account security token.
        self.change_active_state(False)
        self.change_active_state(True)

        # Django may accept the old signing secret during key rotation,
        # but it must not accept the former account security token.
        with override_settings(
            SECRET_KEY=new_secret,
            SECRET_KEY_FALLBACKS=[old_secret],
        ):
            self.assert_denied(self.browser_a)
