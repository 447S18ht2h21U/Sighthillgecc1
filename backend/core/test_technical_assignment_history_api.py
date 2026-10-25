"""Security and pagination tests for Technician assignment history."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Customer,
    Project,
    ProjectTechnicalAssignment,
    Role,
    User,
)


class TechnicalAssignmentHistoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.comptroller = User.objects.create_user(
            username="history_comptroller",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="history_installation_manager",
            role=Role.INSTALLATION_MANAGER,
        )
        self.ceo = User.objects.create_user(
            username="history_ceo",
            role=Role.CEO,
        )
        self.sales_manager = User.objects.create_user(
            username="history_sales_manager",
            role=Role.SALES_MANAGER,
        )
        self.sales_associate = User.objects.create_user(
            username="history_sales_associate",
            role=Role.SALES_ASSOCIATE,
        )
        self.technician = User.objects.create_user(
            username="history_technician",
            first_name="Jordan",
            last_name="Smith",
            role=Role.TECHNICIAN,
        )

        self.customer = Customer.objects.create(
            legal_name="History Test Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )

        self.project = self.make_project("HISTORY-001")
        self.other_project = self.make_project("HISTORY-002")

        self.active_assignment = self.make_assignment(
            self.project,
            date(2026, 10, 10),
        )
        self.ended_assignment = self.make_assignment(
            self.project,
            date(2026, 10, 1),
            ended=True,
        )
        self.other_assignment = self.make_assignment(
            self.other_project,
            date(2026, 10, 5),
        )

    def make_project(self, code):
        return Project.objects.create(
            code=code,
            customer=self.customer,
            location="History Test Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def make_assignment(self, project, effective_date, ended=False):
        return ProjectTechnicalAssignment.objects.create(
            project=project,
            technical_associate=self.technician,
            assigned_by=self.manager,
            effective_date=effective_date,
            status=(
                ProjectTechnicalAssignment.Status.ENDED
                if ended
                else ProjectTechnicalAssignment.Status.ACTIVE
            ),
            ended_at=timezone.now() if ended else None,
        )

    def history(self, actor, project=None, query=""):
        self.client.force_authenticate(user=actor)
        project_id = self.project.pk if project is None else project.pk
        url = f"/api/technical-assignment-history/?project={project_id}"
        return self.client.get(url + query)

    def test_installation_manager_can_view_history(self):
        response = self.history(self.manager)
        self.assertEqual(response.status_code, 200)

    def test_comptroller_can_view_history(self):
        response = self.history(self.comptroller)
        self.assertEqual(response.status_code, 200)

    def test_ceo_can_view_history_without_temporary_authority(self):
        response = self.history(self.ceo)
        self.assertEqual(response.status_code, 403)

    def test_sales_manager_cannot_view_history(self):
        response = self.history(self.sales_manager)
        self.assertEqual(response.status_code, 403)

    def test_sales_associate_cannot_view_history(self):
        response = self.history(self.sales_associate)
        self.assertEqual(response.status_code, 403)

    def test_technician_cannot_view_history(self):
        response = self.history(self.technician)
        self.assertEqual(response.status_code, 403)

    def test_inactive_manager_cannot_view_history(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        response = self.history(self.manager)
        self.assertIn(response.status_code, (401, 403))

    def test_unauthenticated_cannot_view_history(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            f"/api/technical-assignment-history/?project={self.project.pk}"
        )
        self.assertIn(response.status_code, (401, 403))

    def test_missing_project_is_rejected(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get("/api/technical-assignment-history/")
        self.assertEqual(response.status_code, 400)

    def test_invalid_project_is_rejected(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            "/api/technical-assignment-history/?project=invalid"
        )
        self.assertEqual(response.status_code, 400)

    def test_history_excludes_other_project(self):
        response = self.history(self.manager)
        self.assertEqual(response.status_code, 200)

        ids = {str(item["id"]) for item in response.data["results"]}

        self.assertEqual(
            ids,
            {
                str(self.active_assignment.pk),
                str(self.ended_assignment.pk),
            },
        )
        self.assertNotIn(str(self.other_assignment.pk), ids)

    def test_history_includes_active_and_ended_assignments(self):
        response = self.history(self.manager)
        self.assertEqual(response.status_code, 200)

        records = {
            str(item["id"]): item
            for item in response.data["results"]
        }

        self.assertEqual(
            records[str(self.active_assignment.pk)]["status"],
            "ACTIVE",
        )
        self.assertEqual(
            records[str(self.ended_assignment.pk)]["status"],
            "ENDED",
        )
        self.assertIsNotNone(
            records[str(self.ended_assignment.pk)]["ended_at"]
        )

    def test_history_includes_technician_identity(self):
        response = self.history(self.manager)
        self.assertEqual(response.status_code, 200)

        record = response.data["results"][0]

        self.assertEqual(
            record["technician_username"],
            "history_technician",
        )
        self.assertEqual(
            record["technician_first_name"],
            "Jordan",
        )
        self.assertEqual(
            record["technician_last_name"],
            "Smith",
        )
        self.assertNotIn("compensation", record)
        self.assertNotIn("payment", record)

    def test_history_paginates_at_fifty(self):
        for index in range(50):
            self.make_assignment(
                self.project,
                date(2026, 1, 1) + timedelta(days=index),
            )

        response = self.history(self.manager)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 52)
        self.assertEqual(len(response.data["results"]), 50)
        self.assertIsNotNone(response.data["next"])

        second = self.history(self.manager, query="&page=2")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.data["results"]), 2)

    def authorize_ceo_for_project(self):
        from .temporary_duty_services import (
            request_temporary_duty,
            approve_temporary_duty,
        )
        from .temporary_project_access_services import (
            request_temporary_project_access,
            approve_temporary_project_access,
        )

        now = timezone.now()

        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        duty = approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )

        access = request_temporary_project_access(
            employee=self.ceo,
            temporary_duty=duty,
            project=self.project,
            requested_by=self.ceo,
            reason="Project-specific history review.",
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )

        access = approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        return duty, access

    def test_ceo_with_approved_project_access_can_view_history(self):
        self.authorize_ceo_for_project()

        response = self.history(self.ceo)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_ceo_cannot_view_other_project_history(self):
        self.authorize_ceo_for_project()

        response = self.history(
            self.ceo,
            project=self.other_project,
        )

        self.assertEqual(response.status_code, 403)

    def test_expired_ceo_project_access_blocks_history(self):
        from unittest.mock import patch

        _, access = self.authorize_ceo_for_project()

        future = access.ends_at + timedelta(seconds=1)

        with patch(
            "django.utils.timezone.now",
            return_value=future,
        ):
            response = self.history(self.ceo)

        self.assertEqual(response.status_code, 403)

    def test_revoked_ceo_project_access_blocks_history(self):
        from .temporary_project_access_services import (
            revoke_temporary_project_access,
        )

        _, access = self.authorize_ceo_for_project()

        revoke_temporary_project_access(
            authorization_id=access.pk,
            revoked_by=self.comptroller,
            reason="Project coverage withdrawn.",
        )

        response = self.history(self.ceo)

        self.assertEqual(response.status_code, 403)
    def test_history_does_not_modify_assignments(self):
        before = list(
            ProjectTechnicalAssignment.objects
            .order_by("pk")
            .values_list("pk", "status", "ended_at")
        )

        response = self.history(self.manager)
        self.assertEqual(response.status_code, 200)

        after = list(
            ProjectTechnicalAssignment.objects
            .order_by("pk")
            .values_list("pk", "status", "ended_at")
        )

        self.assertEqual(before, after)