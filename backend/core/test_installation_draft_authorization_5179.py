import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core.installation_provider_oauth_4979 import Role
from core import installation_draft_authorization_5179 as auth

FLAG = "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class InspectionDraftAuthorization5179Tests(SimpleTestCase):

    def actor(self, role):
        return SimpleNamespace(pk=1, is_active=True, role=role)

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionDenied):
                auth._gate(self.actor(Role.CEO))

    def test_comptroller_cannot_authorize(self):
        with patch.dict(os.environ, {FLAG: "1"}):
            with self.assertRaises(PermissionDenied):
                auth._gate(self.actor(Role.COMPTROLLER))

    def test_installation_manager_cannot_authorize(self):
        with patch.dict(os.environ, {FLAG: "1"}):
            with self.assertRaises(PermissionDenied):
                auth._gate(self.actor(Role.INSTALLATION_MANAGER))

    def test_inactive_user_cannot_authorize(self):
        with patch.dict(os.environ, {FLAG: "1"}):
            actor = self.actor(Role.CEO)
            actor.is_active = False
            with self.assertRaises(PermissionDenied):
                auth._gate(actor)

    def test_role_must_match_fresh_database_identity(self):
        with (
            patch.dict(os.environ, {FLAG: "1"}),
            patch.object(auth.User.objects, "filter") as query,
        ):
            query.return_value.first.return_value = self.actor(
                Role.COMPTROLLER
            )
            with self.assertRaises(PermissionDenied):
                auth._gate(self.actor(Role.CEO))

    def test_ceo_allowed_with_current_role(self):
        with (
            patch.dict(os.environ, {FLAG: "1"}),
            patch.object(auth.User.objects, "filter") as query,
        ):
            query.return_value.first.return_value = self.actor(Role.CEO)
            self.assertEqual(
                auth._gate(self.actor(Role.CEO)).role,
                Role.CEO,
            )

    def test_sales_manager_allowed_with_current_role(self):
        with (
            patch.dict(os.environ, {FLAG: "1"}),
            patch.object(auth.User.objects, "filter") as query,
        ):
            query.return_value.first.return_value = self.actor(
                Role.SALES_MANAGER
            )
            self.assertEqual(
                auth._gate(self.actor(Role.SALES_MANAGER)).role,
                Role.SALES_MANAGER,
            )

    def test_non_envelope_rejected(self):
        with self.assertRaises(ValidationError):
            auth._fingerprint(object())

    def test_production_rejected_even_when_flag_enabled(self):
        with (
            override_settings(ENVIRONMENT="production", DEBUG=False),
            patch.dict(os.environ, {FLAG: "1"}),
        ):
            with self.assertRaises(PermissionDenied):
                auth._gate(self.actor(Role.CEO))