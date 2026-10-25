"""Rollback safeguards for temporary-authority Technician assignments."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import (
    AuditEvent,
    AuditHead,
    Customer,
    Outbox,
    Project,
    ProjectTechnicalAssignment,
    Role,
    TemporaryDutyActivity,
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


class TemporaryTechnicalAssignmentRollbackTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="rollback_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="rollback_installation_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.ceo = User.objects.create_user(
            username="rollback_temporary_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
        )
        self.technician = User.objects.create_user(
            username="rollback_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(
            legal_name="Temporary Rollback Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="TECH-TEMP-ROLLBACK-001",
            customer=self.customer,
            location="Temporary Rollback Test Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

        now = timezone.now()
        authorization = request_temporary_duty(
            employee=self.ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=self.ceo,
            reason="Temporary installation management coverage.",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        self.authorization = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )

        from .temporary_project_access_services import (
            request_temporary_project_access,
            approve_temporary_project_access,
        )

        access = request_temporary_project_access(
            employee=self.ceo,
            temporary_duty=authorization,
            project=self.project,
            requested_by=self.ceo,
            reason="Project-specific Technician assignment rollback testing.",
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )
        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

    def snapshot(self):
        head = AuditHead.objects.get(pk=1)
        return (
            head.sequence,
            head.digest,
            AuditEvent.objects.count(),
            Outbox.objects.count(),
            TemporaryDutyActivity.objects.count(),
            ProjectTechnicalAssignment.objects.count(),
        )

    def test_creation_rolls_back_if_activity_record_fails(self):
        before = self.snapshot()

        with patch.object(
            TemporaryDutyActivity.objects,
            "create",
            side_effect=RuntimeError("Simulated activity failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated activity failure"
            ):
                create_technical_assignment(
                    actor=self.ceo,
                    project=self.project,
                    technical_associate=self.technician,
                    effective_date=date(2026, 10, 10),
                )

        self.assertEqual(self.snapshot(), before)
        self.assertFalse(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                technical_associate=self.technician,
            ).exists()
        )

    def test_termination_rolls_back_if_activity_record_fails(self):
        assignment = create_technical_assignment(
            actor=self.manager,
            project=self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )
        before = self.snapshot()

        with patch.object(
            TemporaryDutyActivity.objects,
            "create",
            side_effect=RuntimeError("Simulated activity failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated activity failure"
            ):
                end_technical_assignment(
                    actor=self.ceo,
                    assignment_id=assignment.pk,
                )

        assignment.refresh_from_db()
        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertIsNone(assignment.ended_at)
        self.assertEqual(self.snapshot(), before)
