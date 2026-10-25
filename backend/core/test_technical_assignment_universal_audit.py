"""Regression tests for universal Technician assignment audit coverage."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from .models import (
    AuditEvent,
    Customer,
    Project,
    ProjectTechnicalAssignment,
    Role,
    User,
)
from .technical_assignment_services import (
    create_technical_assignment,
    end_technical_assignment,
)


class UniversalTechnicalAssignmentAuditTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="universal_audit_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="universal_audit_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.technician = User.objects.create_user(
            username="universal_audit_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(
            legal_name="Universal Audit Test Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TECH-AUDIT-001",
            customer=self.customer,
            location="Universal Audit Test Location",
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

    def assert_single_event(self, actor, action, assignment):
        events = AuditEvent.objects.filter(
            action=action,
            entity_id=assignment.pk,
        )
        self.assertEqual(events.count(), 1)

        event = events.get()
        self.assertEqual(event.actor_id, actor.pk)
        self.assertEqual(
            event.payload["project_id"],
            str(self.project.pk),
        )
        self.assertEqual(
            event.payload["technical_associate_id"],
            str(self.technician.pk),
        )
        return event

    def test_manager_creation_creates_exactly_one_event(self):
        assignment = self.create_assignment(self.manager)
        event = self.assert_single_event(
            self.manager,
            "TECHNICAL_ASSIGNMENT_CREATED",
            assignment,
        )
        self.assertEqual(
            event.payload["effective_date"],
            "2026-10-10",
        )

    def test_comptroller_creation_creates_exactly_one_event(self):
        assignment = self.create_assignment(self.comptroller)
        self.assert_single_event(
            self.comptroller,
            "TECHNICAL_ASSIGNMENT_CREATED",
            assignment,
        )

    def test_manager_termination_creates_exactly_one_event(self):
        assignment = self.create_assignment(self.manager)
        ended = end_technical_assignment(self.manager, assignment.pk)
        event = self.assert_single_event(
            self.manager,
            "TECHNICAL_ASSIGNMENT_ENDED",
            ended,
        )
        self.assertEqual(
            event.payload["ended_at"],
            ended.ended_at.isoformat(),
        )

    def test_comptroller_termination_creates_exactly_one_event(self):
        assignment = self.create_assignment(self.comptroller)
        ended = end_technical_assignment(self.comptroller, assignment.pk)
        self.assert_single_event(
            self.comptroller,
            "TECHNICAL_ASSIGNMENT_ENDED",
            ended,
        )

    def test_creation_rolls_back_if_audit_fails(self):
        before = ProjectTechnicalAssignment.objects.count()

        with patch(
            "core.services.audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated audit failure"
            ):
                self.create_assignment(self.manager)

        self.assertEqual(
            ProjectTechnicalAssignment.objects.count(),
            before,
        )

    def test_termination_rolls_back_if_audit_fails(self):
        assignment = self.create_assignment(self.manager)

        with patch(
            "core.services.audit",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated audit failure"
            ):
                end_technical_assignment(
                    self.manager,
                    assignment.pk,
                )

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
