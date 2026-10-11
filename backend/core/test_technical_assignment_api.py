"""API regression tests for technical project assignments."""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Customer, Project, ProjectTechnicalAssignment, Role, User


class TechnicalAssignmentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.comptroller = User.objects.create_user(
            username="assignment_api_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="assignment_api_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.technician = User.objects.create_user(
            username="assignment_api_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(
            legal_name="Technical Assignment API Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TECH-API-001",
            customer=self.customer,
            location="Technical Assignment API Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def test_installation_manager_can_create_assignment(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(self.project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": date(2026, 10, 10).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        assignment = ProjectTechnicalAssignment.objects.get()
        self.assertEqual(assignment.project_id, self.project.pk)
        self.assertEqual(assignment.technical_associate_id, self.technician.pk)
        self.assertEqual(assignment.assigned_by_id, self.manager.pk)
        self.assertEqual(assignment.status, ProjectTechnicalAssignment.Status.ACTIVE)
    def test_technician_cannot_create_assignment(self):
        self.client.force_authenticate(self.technician)
        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(self.project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": "2026-10-10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ProjectTechnicalAssignment.objects.exists()
        )
    def test_comptroller_can_create_assignment(self):
        self.client.force_authenticate(self.comptroller)
        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(self.project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": "2026-10-10",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        assignment = ProjectTechnicalAssignment.objects.get()
        self.assertEqual(assignment.project_id, self.project.pk)
        self.assertEqual(
            assignment.technical_associate_id,
            self.technician.pk,
        )
        self.assertEqual(
            assignment.assigned_by_id,
            self.comptroller.pk,
        )
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
    def test_approved_temporary_installation_manager_can_create_assignment(self):
        from datetime import timedelta

        from django.utils import timezone

        from .models import TemporaryDutyActivity
        from .temporary_duty_services import (
            approve_temporary_duty,
            request_temporary_duty,
        )

        temporary_manager = User.objects.create_user(
            username="assignment_api_temporary_manager",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=temporary_manager,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=temporary_manager,
            reason="Temporary installation management coverage",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )

        approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        self.client.force_authenticate(temporary_manager)
        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(self.project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": "2026-10-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        assignment = ProjectTechnicalAssignment.objects.get()
        self.assertEqual(
            assignment.assigned_by_id,
            temporary_manager.pk,
        )

        temporary_manager.refresh_from_db()
        self.assertEqual(
            temporary_manager.role,
            Role.CEO,
        )

        self.assertTrue(
            TemporaryDutyActivity.objects.filter(
                authorization=authorization,
                employee=temporary_manager,
            ).exists()
        )


    def test_installation_manager_can_end_assignment(self):
        from .technical_assignment_services import create_technical_assignment

        assignment = create_technical_assignment(
            actor=self.manager,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"/api/technical-assignments/{assignment.pk}/end/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )
        self.assertIsNotNone(assignment.ended_at)
        self.assertEqual(
            ProjectTechnicalAssignment.objects.count(),
            1,
        )
    def test_technician_cannot_end_assignment(self):
        from .technical_assignment_services import create_technical_assignment

        assignment = create_technical_assignment(
            actor=self.manager,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

        self.client.force_authenticate(self.technician)
        response = self.client.post(
            f"/api/technical-assignments/{assignment.pk}/end/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
    def test_assignment_cannot_be_ended_twice(self):
        from .technical_assignment_services import create_technical_assignment

        assignment = create_technical_assignment(
            actor=self.manager,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

        self.client.force_authenticate(self.manager)
        url = f"/api/technical-assignments/{assignment.pk}/end/"

        first_response = self.client.post(url, {}, format="json")
        self.assertEqual(first_response.status_code, 200)

        assignment.refresh_from_db()
        original_ended_at = assignment.ended_at

        second_response = self.client.post(url, {}, format="json")
        self.assertEqual(second_response.status_code, 400)

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )
        self.assertEqual(assignment.ended_at, original_ended_at)
        self.assertEqual(
            ProjectTechnicalAssignment.objects.count(),
            1,
        )
    def test_cannot_end_nonexistent_assignment(self):
        from uuid import uuid4

        self.client.force_authenticate(self.manager)

        nonexistent_id = uuid4()
        response = self.client.post(
            f"/api/technical-assignments/{nonexistent_id}/end/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            ProjectTechnicalAssignment.objects.exists()
        )
    def test_unauthenticated_user_cannot_create_assignment(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(self.project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": "2026-10-10",
            },
            format="json",
        )

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(
            ProjectTechnicalAssignment.objects.exists()
        )
