from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse, resolve
from rest_framework.exceptions import PermissionDenied

from .installation_schedule_api import InstallationScheduleViewSet
from .installation_schedule_services import create_future_installation_schedule
from .models import Role


class FutureSchedule4565Tests(TestCase):

    def setUp(self):
        self.project_id = uuid4()
        self.manager_id = uuid4()
        self.actor = SimpleNamespace(pk=uuid4())
        self.project = SimpleNamespace(pk=self.project_id)
        self.manager = SimpleNamespace(
            pk=self.manager_id,
            id=self.manager_id,
            role=Role.INSTALLATION_MANAGER,
            is_active=True,
            first_name="Test",
            last_name="Manager",
            username="fictional_installation_manager",
        )
        self.data = {
            "project": str(self.project_id),
            "installation_manager": str(self.manager_id),
            "scheduled_date": "2030-01-10",
        }

    def test_future_schedule_route_registered(self):
        url = reverse("installation-schedules-schedule-future")
        self.assertEqual(
            resolve(url).func.actions["post"], "schedule_future"
        )

    def test_unauthorized_request_denied_before_lookup(self):
        request = SimpleNamespace(user=self.actor, data=self.data)
        with patch(
            "core.installation_schedule_services._authorized_installation_actor",
            side_effect=PermissionDenied("Unauthorized"),
        ), patch(
            "core.installation_schedule_api.get_object_or_404"
        ) as lookup:
            with self.assertRaises(PermissionDenied):
                InstallationScheduleViewSet().schedule_future(request)
            lookup.assert_not_called()

    def test_authorized_route_calls_guarded_service(self):
        request = SimpleNamespace(user=self.actor, data=self.data)
        schedule_id = uuid4()
        schedule = SimpleNamespace(
            pk=schedule_id,
            id=schedule_id,
            project_id=self.project_id,
            project=self.project,
            scheduled_date=date(2030, 1, 10),
            installation_manager=self.manager,
            installation_manager_id=self.manager_id,
            scheduled_by=self.actor,
            scheduled_by_id=self.actor.pk,
            status="SCHEDULED",
            completed_at=None,
            cancelled_at=None,
        )

        with patch(
            "core.installation_schedule_services._authorized_installation_actor",
            return_value=(self.actor, None),
        ), patch(
            "core.installation_schedule_api.operational_project_scope"
        ), patch(
            "core.installation_schedule_api.get_object_or_404",
            side_effect=[self.project, self.manager],
        ), patch(
            "core.installation_schedule_services.create_future_installation_schedule",
            return_value=schedule,
        ) as create:
            result = InstallationScheduleViewSet().schedule_future(request)

        self.assertEqual(result.status_code, 201)
        create.assert_called_once()
        self.assertEqual(
            create.call_args.kwargs["scheduled_date"],
            date(2030, 1, 10),
        )

    def test_inactive_assigned_manager_fails_closed(self):
        self.manager.is_active = False

        with patch(
            "core.installation_schedule_services._authorized_installation_actor",
            return_value=(self.actor, None),
        ), patch(
            "core.installation_schedule_services._require_project_access"
        ):
            with self.assertRaises(PermissionDenied):
                create_future_installation_schedule(
                    actor=self.actor,
                    project=self.project,
                    scheduled_date=date(2030, 1, 10),
                    installation_manager=self.manager,
                )