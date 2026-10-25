"""Real temporary-project-access lifecycle tests for Technician assignments."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import (
    AuditEvent,
    Customer,
    Outbox,
    Project,
    ProjectTechnicalAssignment,
    Role,
    TemporaryDutyAuthorization,
    User,
)
from .technical_assignment_services import (
    create_technical_assignment,
    end_technical_assignment,
)
from .temporary_duty_services import (
    approve_temporary_duty,
    request_temporary_duty,
)
from .temporary_project_access_services import (
    approve_temporary_project_access,
    request_temporary_project_access,
    revoke_temporary_project_access,
)


class TechnicianAssignmentAccessLifecycleTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="lifecycle_comptroller",
            role=Role.COMPTROLLER,
        )
        self.ceo = User.objects.create_user(
            username="lifecycle_ceo",
            role=Role.CEO,
        )
        self.technician = User.objects.create_user(
            username="lifecycle_technician",
            role=Role.TECHNICIAN,
        )
        customer = Customer.objects.create(
            legal_name="Technician Lifecycle Customer",
            billing_address="123 Example Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TECH-LIFECYCLE-001",
            customer=customer,
            location="Project One",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )
        self.other_project = Project.objects.create(
            code="TECH-LIFECYCLE-002",
            customer=customer,
            location="Project Two",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

        self.now = timezone.now()
        duty = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation coverage.",
            starts_at=self.now - timedelta(minutes=1),
            ends_at=self.now + timedelta(days=2),
        )
        self.duty = approve_temporary_duty(
            authorization_id=duty.pk,
            approver=self.comptroller,
        )

    def request_access(self):
        return request_temporary_project_access(
            employee=self.ceo,
            temporary_duty=self.duty,
            project=self.project,
            requested_by=self.ceo,
            reason="Project-specific technician assignment coverage.",
            starts_at=self.now,
            ends_at=self.now + timedelta(days=1),
        )

    def approve_access(self):
        access = self.request_access()
        return approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

    def create_assignment(self, project=None):
        return create_technical_assignment(
            actor=self.ceo,
            project=project if project is not None else self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

    def create_existing_assignment(self):
        return create_technical_assignment(
            actor=self.comptroller,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

    def snapshot(self):
        return (
            ProjectTechnicalAssignment.objects.count(),
            AuditEvent.objects.count(),
            Outbox.objects.count(),
        )

    def assert_creation_denied_unchanged(self, project=None):
        before = self.snapshot()
        with self.assertRaises(PermissionDenied):
            self.create_assignment(project)
        self.assertEqual(self.snapshot(), before)

    def assert_termination_denied_unchanged(self, assignment):
        before = self.snapshot()
        with self.assertRaises(PermissionDenied):
            end_technical_assignment(self.ceo, assignment.pk)
        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertEqual(self.snapshot(), before)

    def test_duty_alone_does_not_allow_creation_or_termination(self):
        existing = self.create_existing_assignment()
        self.assert_creation_denied_unchanged()
        self.assert_termination_denied_unchanged(existing)

    def test_pending_access_does_not_allow_creation_or_termination(self):
        existing = self.create_existing_assignment()
        self.request_access()
        self.assert_creation_denied_unchanged()
        self.assert_termination_denied_unchanged(existing)

    def test_approved_access_allows_creation_and_termination(self):
        self.approve_access()
        assignment = self.create_assignment()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        ended = end_technical_assignment(self.ceo, assignment.pk)
        self.assertEqual(
            ended.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )

    def test_approved_access_does_not_extend_to_other_project(self):
        self.approve_access()
        self.assert_creation_denied_unchanged(self.other_project)

    def test_revoked_access_blocks_creation_and_termination(self):
        existing = self.create_existing_assignment()
        access = self.approve_access()
        revoke_temporary_project_access(
            authorization_id=access.pk,
            revoked_by=self.comptroller,
            reason="Project coverage withdrawn.",
        )
        self.assert_creation_denied_unchanged()
        self.assert_termination_denied_unchanged(existing)

        self.duty.refresh_from_db()
        self.assertEqual(
            self.duty.status,
            TemporaryDutyAuthorization.Status.APPROVED,
        )

    def test_expired_access_blocks_creation_and_termination(self):
        existing = self.create_existing_assignment()
        access = self.approve_access()
        simulated_time = access.ends_at + timedelta(seconds=1)

        with patch(
            "core.operational_visibility.timezone.now",
            return_value=simulated_time,
        ):
            self.assert_creation_denied_unchanged()
            self.assert_termination_denied_unchanged(existing)
