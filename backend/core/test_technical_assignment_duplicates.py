"""Regression tests for Technician assignment duplicate prevention."""

from datetime import date
from unittest.mock import patch
from django.db import IntegrityError

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

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


NOTICE = (
    "This Technician already has an active assignment to this project. "
    "Review the active assignments below. "
    "You do not need to create another assignment."
)


class TechnicalAssignmentDuplicateTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="duplicate_test_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="duplicate_test_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.technician = User.objects.create_user(
            username="duplicate_test_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(
            legal_name="Duplicate Assignment Test Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = self.make_project("TECH-DUP-001")
        self.other_project = self.make_project("TECH-DUP-002")
        self.client = APIClient()

    def make_project(self, code):
        return Project.objects.create(
            code=code,
            customer=self.customer,
            location="Duplicate Assignment Test Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def create_assignment(self, project=None):
        return create_technical_assignment(
            actor=self.manager,
            project=project or self.project,
            technical_associate=self.technician,
            effective_date=date(2026, 10, 10),
        )

    def snapshot(self):
        head = AuditHead.objects.get(pk=1)
        return (
            ProjectTechnicalAssignment.objects.count(),
            AuditEvent.objects.count(),
            Outbox.objects.count(),
            head.sequence,
            head.digest,
        )

    def test_sqlite_unique_conflict_gives_clear_notice(self):
        cause = Exception(
            "UNIQUE constraint failed: "
            "core_projecttechnicalassignment.project_id, "
            "core_projecttechnicalassignment.technical_associate_id"
        )
        failure = IntegrityError("Simulated SQLite conflict")
        failure.__cause__ = cause
        before = self.snapshot()

        with patch.object(
            ProjectTechnicalAssignment.objects,
            "create",
            side_effect=failure,
        ):
            with self.assertRaises(ValidationError) as caught:
                self.create_assignment()

        self.assertEqual(str(caught.exception.detail[0]), NOTICE)
        self.assertEqual(self.snapshot(), before)

    def test_postgresql_named_constraint_gives_clear_notice(self):
        class PostgreSQLCause(Exception):
            def __init__(self):
                self.diag = type(
                    "Diagnostic",
                    (),
                    {"constraint_name": "unique_active_technician_per_project"},
                )()
                super().__init__("Simulated PostgreSQL uniqueness violation")

        failure = IntegrityError("Simulated PostgreSQL conflict")
        failure.__cause__ = PostgreSQLCause()
        before = self.snapshot()

        with patch.object(
            ProjectTechnicalAssignment.objects,
            "create",
            side_effect=failure,
        ):
            with self.assertRaises(ValidationError) as caught:
                self.create_assignment()

        self.assertEqual(str(caught.exception.detail[0]), NOTICE)
        self.assertEqual(self.snapshot(), before)

    def test_unrelated_integrity_error_is_not_disguised(self):
        failure = IntegrityError("Simulated unrelated integrity failure")
        before = self.snapshot()

        with patch.object(
            ProjectTechnicalAssignment.objects,
            "create",
            side_effect=failure,
        ):
            with self.assertRaises(IntegrityError):
                self.create_assignment()

        self.assertEqual(self.snapshot(), before)
    def test_duplicate_is_rejected_without_assignment_or_audit_changes(self):
        self.create_assignment()
        before = self.snapshot()

        with self.assertRaises(ValidationError) as caught:
            self.create_assignment()

        self.assertEqual(str(caught.exception.detail[0]), NOTICE)
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_api_returns_clear_notice_without_changes(self):
        self.create_assignment()
        before = self.snapshot()

        self.client.force_authenticate(self.manager)
        response = self.client.post(
            "/api/technical-assignments/",
            {
                "project": str(self.project.pk),
                "technical_associate": str(self.technician.pk),
                "effective_date": "2026-10-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data[0]), NOTICE)
        self.assertEqual(self.snapshot(), before)

    def test_same_technician_can_work_on_different_projects(self):
        first = self.create_assignment()
        second = self.create_assignment(self.other_project)

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            ProjectTechnicalAssignment.objects.filter(
                technical_associate=self.technician,
                status=ProjectTechnicalAssignment.Status.ACTIVE,
            ).count(),
            2,
        )

    def test_reassignment_after_end_preserves_history(self):
        first = self.create_assignment()
        end_technical_assignment(self.manager, first.pk)

        replacement = self.create_assignment()
        first.refresh_from_db()

        self.assertEqual(
            first.status,
            ProjectTechnicalAssignment.Status.ENDED,
        )
        self.assertIsNotNone(first.ended_at)
        self.assertNotEqual(first.pk, replacement.pk)
        self.assertEqual(
            ProjectTechnicalAssignment.objects.filter(
                project=self.project,
                technical_associate=self.technician,
            ).count(),
            2,
        )
        self.assertEqual(
            replacement.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )

    def test_unauthorized_user_does_not_receive_duplicate_notice(self):
        self.create_assignment()
        before = self.snapshot()

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
        self.assertNotIn(NOTICE, str(response.data))
        self.assertEqual(self.snapshot(), before)
