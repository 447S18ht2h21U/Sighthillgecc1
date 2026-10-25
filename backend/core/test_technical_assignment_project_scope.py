"""Project-scope security tests for Technician assignments."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from .models import (
    AuditEvent,
    Customer,
    Outbox,
    Project,
    ProjectTechnicalAssignment,
    Role,
    User,
)
from .technical_assignment_services import (
    create_technical_assignment,
    end_technical_assignment,
)


class TechnicianAssignmentProjectScopeTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="scope_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="scope_installation_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.technician = User.objects.create_user(
            username="scope_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        customer = Customer.objects.create(
            legal_name="Technician Scope Test Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TECH-SCOPE-001",
            customer=customer,
            location="Scope Test Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def create_assignment(self, actor):
        return create_technical_assignment(
            actor=actor,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

    def counts(self):
        return (
            ProjectTechnicalAssignment.objects.count(),
            AuditEvent.objects.count(),
            Outbox.objects.count(),
        )

    def test_creation_rejected_when_project_scope_denied(self):
        before = self.counts()

        with patch(
            "core.operational_visibility.operational_project_scope"
        ) as scope:
            # The service must use the shared operational scope.
            scope.return_value = Project.objects.none()

            with self.assertRaises(PermissionDenied):
                self.create_assignment(self.manager)

        self.assertEqual(self.counts(), before)

    def test_termination_rejected_when_project_scope_denied(self):
        assignment = self.create_assignment(self.manager)
        before = self.counts()

        with patch(
            "core.operational_visibility.operational_project_scope"
        ) as scope:
            scope.return_value = Project.objects.none()

            with self.assertRaises(PermissionDenied):
                end_technical_assignment(
                    actor=self.manager,
                    assignment_id=assignment.pk,
                )

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertEqual(self.counts(), before)

    def test_permanent_manager_can_assign_in_scope(self):
        assignment = self.create_assignment(self.manager)
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )

    def test_comptroller_can_end_in_scope(self):
        assignment = self.create_assignment(self.manager)
        ended = end_technical_assignment(
            actor=self.comptroller,
            assignment_id=assignment.pk,
        )
        self.assertEqual(
            ended.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )
