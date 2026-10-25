"""Transaction integrity tests for Technician assignment auditing."""

from datetime import date
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
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


class TechnicalAssignmentAuditIntegrityTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="integrity_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="integrity_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.technician = User.objects.create_user(
            username="integrity_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(
            legal_name="Audit Integrity Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TECH-INTEGRITY-001",
            customer=self.customer,
            location="Audit Integrity Test Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def create_assignment(self):
        return create_technical_assignment(
            actor=self.manager,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

    def snapshot(self):
        head = AuditHead.objects.get(pk=1)
        return (
            head.sequence,
            head.digest,
            AuditEvent.objects.count(),
            Outbox.objects.count(),
            ProjectTechnicalAssignment.objects.count(),
        )

    def test_successful_creation_has_matching_outbox(self):
        assignment = self.create_assignment()

        event = AuditEvent.objects.get(
            action="TECHNICAL_ASSIGNMENT_CREATED",
            entity_id=assignment.pk,
        )
        outbox = Outbox.objects.get(event=event)

        self.assertEqual(outbox.topic, event.action)
        self.assertEqual(
            outbox.payload["audit_id"],
            str(event.pk),
        )
        call_command("verify_audit")

    def test_successful_termination_has_matching_outbox(self):
        assignment = self.create_assignment()
        end_technical_assignment(self.manager, assignment.pk)

        event = AuditEvent.objects.get(
            action="TECHNICAL_ASSIGNMENT_ENDED",
            entity_id=assignment.pk,
        )
        outbox = Outbox.objects.get(event=event)

        self.assertEqual(outbox.topic, event.action)
        self.assertEqual(AuditEvent.objects.count(), Outbox.objects.count())
        call_command("verify_audit")

    def test_creation_rolls_back_when_outbox_creation_fails(self):
        before = self.snapshot()

        with patch.object(
            Outbox.objects,
            "create",
            side_effect=RuntimeError("Simulated outbox failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated outbox failure"
            ):
                self.create_assignment()

        self.assertEqual(self.snapshot(), before)
        call_command("verify_audit")

    def test_termination_rolls_back_when_outbox_creation_fails(self):
        assignment = self.create_assignment()
        before = self.snapshot()

        with patch.object(
            Outbox.objects,
            "create",
            side_effect=RuntimeError("Simulated outbox failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated outbox failure"
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
        self.assertEqual(self.snapshot(), before)
        call_command("verify_audit")
