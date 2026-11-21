"""Real database authorization checks for the IM workspace."""
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from core.models import Role, User
from core.installation_manager_workspace_5211 import workspace
from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationManagerWorkspace5211(TestCase):
    setUp = Fixture.setUp
    def request(self, actor):
        request = APIRequestFactory().get("/api/im-inspection-workspace/")
        force_authenticate(request, user=actor)
        return workspace(request, self.project.pk)
    def test_assigned_manager_sees_five_questions_without_authority(self):
        response = self.request(self.inspector)
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(
            data["state"], "READY_FOR_INSPECTION_REVIEW"
        )
        self.assertEqual(len(data["questions"]), 5)
        self.assertTrue(data["approved_msr"])
        self.assertTrue(data["completed_schedule"])
        for key in (
            "answers_recorded_by_this_endpoint",
            "provider_signature_verified",
            "signed_date_verified",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertIs(data[key], False)
    def test_other_role_and_unassigned_manager_denied(self):
        self.assertEqual(self.request(self.reviewer).status_code, 403)
        other = User.objects.create_user(
            username="im_workspace_5211_other",
            role=Role.INSTALLATION_MANAGER,
            initials="OI",
        )
        self.assertEqual(self.request(other).status_code, 403)
    def test_completed_installation_cannot_be_reopened(self):
        from django.db import IntegrityError, transaction
        from core.models import InstallationSchedule
        original_completed_at = self.schedule.completed_at
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.schedule.status = InstallationSchedule.Status.SCHEDULED
                self.schedule.completed_at = None
                self.schedule.save(
                    update_fields=["status", "completed_at"]
                )
        self.schedule.refresh_from_db()
        self.assertEqual(
            self.schedule.status,
            InstallationSchedule.Status.COMPLETED,
        )
        self.assertEqual(
            self.schedule.completed_at,
            original_completed_at,
        )
        result = self.request(self.inspector)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.data["state"],
            "READY_FOR_INSPECTION_REVIEW",
        )
        self.assertTrue(result.data["completed_schedule"])
        self.assertFalse(
            result.data["provider_signature_verified"]
        )
        self.assertFalse(
            result.data["project_completion_authorized"]
        )
    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        self.assertEqual(self.request(self.inspector).status_code, 403)
