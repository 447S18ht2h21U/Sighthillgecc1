from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.urls import resolve, reverse
from rest_framework.exceptions import PermissionDenied

from .installation_schedule_api import InstallationScheduleViewSet


class ProposedDateApi4565Tests(SimpleTestCase):

    def test_route_registered(self):
        url = reverse("installation-schedules-assess-proposed-date")
        self.assertEqual(
            resolve(url).func.actions["post"],
            "assess_proposed_date",
        )

    def test_unauthorized_actor_denied_before_project_lookup(self):
        view = InstallationScheduleViewSet()
        request = SimpleNamespace(
            user=SimpleNamespace(pk=uuid4()),
            data={"project": str(uuid4()), "scheduled_date": "2030-01-10"},
        )
        with patch(
            "core.installation_schedule_services._authorized_installation_actor",
            side_effect=PermissionDenied("Unauthorized"),
        ), patch(
            "core.installation_schedule_api.get_object_or_404"
        ) as lookup:
            with self.assertRaises(PermissionDenied):
                view.assess_proposed_date(request)
            lookup.assert_not_called()

    def test_readiness_does_not_grant_installation_authority(self):
        actor = SimpleNamespace(pk=uuid4())
        project = SimpleNamespace(pk=uuid4())
        msr = SimpleNamespace(pk=uuid4())
        request = SimpleNamespace(
            user=actor,
            data={"project": str(project.pk), "scheduled_date": "2030-01-10"},
        )
        view = InstallationScheduleViewSet()

        with patch(
            "core.installation_schedule_services._authorized_installation_actor",
            return_value=(actor, None),
        ), patch(
            "core.installation_schedule_api.operational_project_scope"
        ), patch(
            "core.installation_schedule_api.get_object_or_404",
            return_value=project,
        ), patch(
            "core.installation_eligibility.require_current_approved_msr",
            return_value=msr,
        ), patch(
            "core.installation_eligibility.verified_signature_time",
            return_value=datetime.fromisoformat("2029-12-01T09:00:00-05:00"),
        ), patch(
            "core.installation_eligibility.cancellation_deadline",
            return_value=datetime.fromisoformat("2029-12-06T09:00:00-05:00"),
        ), patch(
            "core.installation_future_date_policy_4565.assess_future_installation_date",
            return_value={
                "normal_date_eligible": True,
                "earliest_at": datetime.fromisoformat("2029-12-06T09:00:00-05:00"),
            },
        ), patch(
            "core.installation_payment_readiness.installation_payment_readiness",
            return_value={"payment_ready": True, "explanation": "Verified"},
        ):
            result = view.assess_proposed_date(request).data

        self.assertTrue(result["scheduling_candidate"])
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["installation_started"])
        self.assertFalse(result["expedited_authorized"])
