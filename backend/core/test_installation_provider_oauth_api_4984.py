"""Endpoint authorization, confirmation, session and routing acceptance."""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Role

M = "core.installation_provider_oauth_api_4984"
PROJECT = "11111111-1111-4111-8111-111111111111"
BINDING = "22222222-2222-4222-8222-222222222222"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationInspectionOAuthEndpoint4984Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.comptroller = User.objects.create_user(
            username="inspection-api-comptroller-4984",
            password=None,
            role=Role.COMPTROLLER,
            initials="IC",
        )
        cls.technician = User.objects.create_user(
            username="inspection-api-technician-4984",
            password=None,
            role=Role.TECHNICIAN,
            initials="IT",
        )

    def call(self, user=None, payload=None, session=True):
        from .installation_provider_oauth_api_4984 import connect

        request = APIRequestFactory().post(
            reverse(
                "installation-inspection-oauth-4984",
                kwargs={"project_id": PROJECT},
            ),
            payload if payload is not None else {
                "binding_id": BINDING,
                "sandbox_read_confirmed": True,
            },
            format="json",
        )
        force_authenticate(
            request, user=user or self.comptroller
        )
        if session:
            request.session = SimpleNamespace(
                session_key="isolated-browser-session-4984"
            )
        return connect(request, project_id=PROJECT)

    @patch(M + ".begin")
    def test_authorized_request_creates_read_only_challenge(self, begin):
        begin.return_value = {
            "authorization_url":
                "https://account-d.docusign.com/oauth/auth?state=synthetic",
            "operation": "SANDBOX_INSPECTION_READ",
            "send_enabled": False,
            "provider_signature_verified": False,
            "project_completion_authorized": False,
        }
        with patch(
            M + ".connections"
        ) as connections:
            connections.__getitem__.return_value.introspection.table_names.return_value = [
                "core_installationinspectionevidence4969",
                "core_projectevidence",
            ]
            # Avoid assuming the model's physical table name.
            from .models import (
                InstallationInspectionEvidence4969,
                ProjectEvidence,
            )
            names = [
                InstallationInspectionEvidence4969._meta.db_table,
                ProjectEvidence._meta.db_table,
            ]
            connections.__getitem__.return_value.introspection.table_names.return_value = names

            response = self.call()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Cache-Control"], "private, no-store"
        )
        self.assertFalse(response.data["send_enabled"])
        self.assertFalse(response.data["provider_signature_verified"])
        begin.assert_called_once()
        self.assertEqual(
            begin.call_args.kwargs["binding_id"], BINDING
        )

    def test_unconfirmed_request_denied(self):
        response = self.call(payload={
            "binding_id": BINDING,
            "sandbox_read_confirmed": False,
        })
        self.assertEqual(response.status_code, 400)

    def test_wrong_role_denied(self):
        response = self.call(user=self.technician)
        self.assertEqual(response.status_code, 403)

    def test_no_session_denied(self):
        with patch(M + ".connections") as connections:
            from .models import (
                InstallationInspectionEvidence4969,
                ProjectEvidence,
            )
            connections.__getitem__.return_value.introspection.table_names.return_value = [
                InstallationInspectionEvidence4969._meta.db_table,
                ProjectEvidence._meta.db_table,
            ]
            response = self.call(session=False)
        self.assertEqual(response.status_code, 400)

    def test_disabled_feature_denied(self):
        with patch(
            "core.installation_provider_oauth_4979.os.environ",
            {},
        ):
            response = self.call()
        self.assertEqual(response.status_code, 403)

    def test_schema_unavailable_fails_closed(self):
        with patch(M + ".connections") as connections:
            connections.__getitem__.return_value.introspection.table_names.return_value = []
            response = self.call()
        self.assertEqual(response.status_code, 400)

    def test_endpoint_path_is_registered(self):
        path = reverse(
            "installation-inspection-oauth-4984",
            kwargs={"project_id": PROJECT},
        )
        self.assertEqual(
            path,
            f"/api/inspection-evidence/{PROJECT}/oauth-read/",
        )
