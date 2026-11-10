from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .installation_start_control_4565 import assess_installation_start
from .models import Role, User


class InstallationStartControl4565Tests(TestCase):

    def setUp(self):
        self.url = reverse("installation-schedules-assess-start")
        self.project = SimpleNamespace(pk=uuid4())

    def test_route_registered(self):
        self.assertEqual(
            resolve(self.url).func.actions["post"],
            "assess_installation_start",
        )

    def test_anonymous_access_denied(self):
        response = APIClient().post(
            self.url,
            {
                "project": str(self.project.pk),
                "proposed_start": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_valid_schedule_and_payment_never_grant_start(self):
        schedule = SimpleNamespace(
            schedule_verified=True,
            blockers=(),
        )
        with patch(
            "core.installation_start_control_4565.assess_database_schedule",
            return_value=schedule,
        ), patch(
            "core.installation_start_control_4565.ensure_installation_eligible",
            return_value=True,
        ):
            result = assess_installation_start(
                project=self.project,
                proposed_start=timezone.now() - timedelta(seconds=1),
            )

        self.assertTrue(result["schedule_verified"])
        self.assertTrue(result["commercial_ready"])
        self.assertFalse(result["trusted_equipment_verified"])
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["installation_started"])
        self.assertTrue(result["blockers"])

    def test_failed_schedule_and_payment_stay_blocked(self):
        schedule = SimpleNamespace(
            schedule_verified=False,
            blockers=("No matching active installation schedule.",),
        )
        from rest_framework.exceptions import ValidationError

        with patch(
            "core.installation_start_control_4565.assess_database_schedule",
            return_value=schedule,
        ), patch(
            "core.installation_start_control_4565.ensure_installation_eligible",
            side_effect=ValidationError("Deposit not verified."),
        ):
            result = assess_installation_start(
                project=self.project,
                proposed_start=timezone.now(),
            )

        self.assertFalse(result["schedule_verified"])
        self.assertFalse(result["commercial_ready"])
        self.assertFalse(result["installation_authorized"])
        self.assertGreaterEqual(len(result["blockers"]), 2)

    def test_manager_endpoint_never_reports_authority(self):
        manager = User.objects.create_user(
            username="fictional_start_assessor_4565",
            password="test-password",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )
        client = APIClient()
        client.force_authenticate(user=manager)
        payload = {
            "project": str(self.project.pk),
            "proposed_start": timezone.now().isoformat(),
        }
        result = {
            "project_id": str(self.project.pk),
            "schedule_verified": True,
            "commercial_ready": True,
            "trusted_equipment_verified": False,
            "expedited_authorized": False,
            "installation_authorized": False,
            "installation_started": False,
            "blockers": ["Trusted equipment evidence unavailable."],
        }

        with patch(
            "core.installation_schedule_services._authorized_installation_actor",
            return_value=(manager, None),
        ), patch(
            "core.installation_schedule_api.operational_project_scope",
        ), patch(
            "core.installation_schedule_api.get_object_or_404",
            return_value=self.project,
        ), patch(
            "core.installation_start_control_4565.assess_installation_start",
            return_value=result,
        ):
            response = client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["installation_authorized"], False)
        self.assertIs(response.data["installation_started"], False)
